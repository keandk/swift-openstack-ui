""" Standalone webinterface for Openstack Swift. """
# -*- coding: utf-8 -*-
import os
import time
import hmac
from hashlib import sha1
from urllib.parse import urlparse

from swiftclient import client

from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.utils.translation import gettext as _
from django.urls import reverse

from swiftapp.forms import CreateContainerForm, PseudoFolderForm, \
    LoginForm, AddACLForm
from swiftapp.utils import replace_hyphens, prefix_list, \
    pseudofolder_object_list, get_temp_key, get_base_url, get_temp_url

import swiftapp


def login(request):
    request.session.flush()
    form = LoginForm(request.POST or None)
    if form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        try:
            auth_version = getattr(settings, 'SWIFT_AUTH_VERSION', '3')
            os_options = {
                'user_domain_name': settings.SWIFT_USER_DOMAIN_NAME,
                'project_domain_name': settings.SWIFT_PROJECT_DOMAIN_NAME,
                'project_name': settings.SWIFT_PROJECT_NAME,
            }
            
            storage_url, auth_token = client.get_auth(
                settings.SWIFT_AUTH_URL,
                username,
                password,
                auth_version=auth_version,
                os_options=os_options
            )
            
            request.session['auth_token'] = auth_token
            request.session['storage_url'] = storage_url
            request.session['username'] = username
            return redirect('containerview')
            
        except client.ClientException as e:
            messages.error(request, f"Login failed: {str(e)}")
            
    return render(request, 'login.html', {'form': form})


def containerview(request):
    """ Returns a list of all containers in current account. """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    try:
        account_stat, containers = client.get_account(storage_url, auth_token)
        account_stat = replace_hyphens(account_stat)

        return render(request, 'containerview.html', {
            'account_stat': account_stat,
            'containers': containers,
            'session': request.session
        })

    except client.ClientException as exc:
        if exc.http_status == 403:
            account_stat = {}
            containers = []
            base_url = get_base_url(request)
            msg = 'Container listing failed. You can manually choose a known '
            msg += 'container by appending the name to the URL, for example: '
            msg += '<a href="%s/objects/containername">' % base_url
            msg += '%s/objects/containername</a>' % base_url
            messages.add_message(request, messages.ERROR, msg)
        else:
            return redirect(login)



def create_container(request):
    """ Creates a container (empty object of type application/directory) """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    form = CreateContainerForm(request.POST or None)
    if form.is_valid():
        container = form.cleaned_data['containername']
        try:
            client.put_container(storage_url, auth_token, container)
            messages.add_message(request, messages.INFO,
                                 _("Container created."))
        except client.ClientException:
            messages.add_message(request, messages.ERROR, _("Access denied."))

        return redirect(containerview)

    return render(request, 'create_container.html', {})


def delete_container(request, container):
    """ Deletes a container """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    try:
        _m, objects = client.get_container(storage_url, auth_token, container)
        for obj in objects:
            client.delete_object(storage_url, auth_token,
                                 container, obj['name'])
        client.delete_container(storage_url, auth_token, container)
        messages.add_message(request, messages.INFO, _("Container deleted."))
    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))

    return redirect(containerview)


def objectview(request, container, prefix=None):
    """ Returns list of all objects in current container. """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    try:
        meta, objects = client.get_container(storage_url, auth_token,
                                             container, delimiter='/',
                                             prefix=prefix)

    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(containerview)

    prefixes = prefix_list(prefix)
    pseudofolders, objs = pseudofolder_object_list(objects, prefix)
    base_url = get_base_url(request)
    account = storage_url.split('/')[-1]

    read_acl = meta.get('x-container-read', '').split(',')
    public = False
    required_acl = ['.r:*', '.rlistings']
    if [x for x in read_acl if x in required_acl]:
        public = True

    return render(request, "objectview.html", {
        'container': container,
        'objects': objs,
        'folders': pseudofolders,
        'session': request.session,
        'prefix': prefix,
        'prefixes': prefixes,
        'base_url': base_url,
        'account': account,
        'public': public})


def upload(request, container, prefix=None):
    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')
    
    if not auth_token:
        messages.error(request, _("Please login first"))
        return redirect('login')

    try:
        # Verify container exists and user has access
        client.head_container(storage_url, auth_token, container)
    except client.ClientException:
        messages.error(request, _("Access denied or container not found"))
        return redirect('containerview')

    # Build redirect URL
    redirect_url = get_base_url(request)
    redirect_url += reverse('objectview', kwargs={'container': container})
    if prefix:
        redirect_url += prefix

    # Build Swift URL
    swift_url = storage_url + '/' + container + '/'
    if prefix:
        swift_url += prefix

    # Generate temporary URL parameters
    max_file_size = 5 * 1024 * 1024 * 1024  # 5GB
    max_file_count = 1
    expires = int(time.time() + 15 * 60)  # 15 minutes
    
    key = get_temp_key(storage_url, auth_token)
    if not key:
        messages.error(request, _("Could not generate upload URL"))
        return redirect('objectview', container=container)

    # Generate HMAC signature
    path = urlparse(swift_url).path
    hmac_body = f'{path}\n{redirect_url}\n{max_file_size}\n{max_file_count}\n{expires}'
    signature = hmac.new(key.encode('utf-8'), hmac_body.encode('utf-8'), sha1).hexdigest()

    return render(request, 'upload_form.html', {
        'swift_url': swift_url,
        'redirect_url': redirect_url,
        'max_file_size': max_file_size,
        'max_file_count': max_file_count,
        'expires': expires,
        'signature': signature,
        'container': container,
        'prefix': prefix,
        'prefixes': prefix_list(prefix)
    })


def download(request, container, objectname):
    """ Download an object from Swift """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')
    url = swiftapp.utils.get_temp_url(storage_url, auth_token,
                                          container, objectname)
    if not url:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(objectview, container=container)

    return redirect(url)


def delete_object(request, container, objectname):
    """ Deletes an object """
    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')
    
    try:
        client.delete_object(storage_url, auth_token, container, objectname)
        messages.add_message(request, messages.INFO, _("Object deleted."))
    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        
    # Calculate prefix for redirection
    if objectname.endswith('/'):  # deleting a pseudofolder
        objectname = objectname[:-1]
    prefix = '/'.join(objectname.split('/')[:-1])
    
    # Redirect with or without prefix
    if prefix:
        return redirect('objectview', container=container, prefix=prefix+'/')
    return redirect('objectview', container=container)


def toggle_public(request, container):
    """ Sets/unsets '.r:*,.rlistings' container read ACL """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    try:
        meta = client.head_container(storage_url, auth_token, container)
    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(containerview)

    read_acl = meta.get('x-container-read', '')
    if '.rlistings' and '.r:*' in read_acl:
        read_acl = read_acl.replace('.r:*', '')
        read_acl = read_acl.replace('.rlistings', '')
        read_acl = read_acl.replace(',,', ',')
    else:
        read_acl += '.r:*,.rlistings'
    headers = {'X-Container-Read': read_acl, }

    try:
        client.post_container(storage_url, auth_token, container, headers)
    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))

    return redirect(objectview, container=container)


def public_objectview(request, account, container, prefix=None):
    """ Returns list of all objects in current container. """
    storage_url = settings.STORAGE_URL + account
    auth_token = b''
    try:
        _meta, objects = client.get_container(
            storage_url, auth_token, container, delimiter='/', prefix=prefix)

    except client.ClientException:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(containerview)

    prefixes = prefix_list(prefix)
    pseudofolders, objs = pseudofolder_object_list(objects, prefix)
    base_url = get_base_url(request)
    account = storage_url.split('/')[-1]

    return render(request, "publicview.html", {
        'container': container,
        'objects': objs,
        'folders': pseudofolders,
        'prefix': prefix,
        'prefixes': prefixes,
        'base_url': base_url,
        'storage_url': storage_url,
        'account': account})


def tempurl(request, container, objectname):
    """ Displays a temporary URL for a given container object """

    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    url = get_temp_url(storage_url, auth_token,
                       container, objectname, 7 * 24 * 3600)

    if not url:
        messages.add_message(request, messages.ERROR, _("Access denied."))
        return redirect(objectview, container=container)

    prefix = '/'.join(objectname.split('/')[:-1])
    if prefix:
        prefix += '/'
    prefixes = prefix_list(prefix)

    return render(request, 'tempurl.html', {
        'url': url,
        'account': storage_url.split('/')[-1],
        'container': container,
        'prefix': prefix,
        'prefixes': prefixes,
        'objectname': objectname,
        'session': request.session})


def create_pseudofolder(request, container, prefix=None):
    """ Creates a pseudofolder (empty object of type application/directory) """
    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    form = PseudoFolderForm(request.POST)
    if form.is_valid():
        foldername = request.POST.get('foldername', None)
        if prefix:
            foldername = prefix + '/' + foldername
        foldername = os.path.normpath(foldername)
        foldername = foldername.strip('/')
        foldername += '/'

        content_type = 'application/directory'
        obj = None

        try:
            client.put_object(storage_url, auth_token,
                              container, foldername, obj,
                              content_type=content_type)
            messages.add_message(request, messages.INFO,
                                 _("Pseudofolder created."))
        except client.ClientException:
            messages.add_message(request, messages.ERROR, _("Access denied."))

        if prefix:
            return redirect(objectview, container=container, prefix=prefix)
        return redirect(objectview, container=container)

    return render(request, 'create_pseudofolder.html', {
        'container': container, 'prefix': prefix})


def get_acls(storage_url, auth_token, container):
    """ Returns ACLs of given container. """
    cont = client.head_container(storage_url, auth_token, container)
    readers = cont.get('x-container-read', '')
    writers = cont.get('x-container-write', '')
    return (readers, writers)


def remove_duplicates_from_acl(acls):
    """ Removes possible duplicates from a comma-separated list. """
    entries = acls.split(',')
    cleaned_entries = list(set(entries))
    acls = ','.join(cleaned_entries)
    return acls


def edit_acl(request, container):
    """Handles ACL operations with Keystone support"""
    storage_url = request.session.get('storage_url', '')
    auth_token = request.session.get('auth_token', '')

    try:
        meta = client.head_container(storage_url, auth_token, container)
    except client.ClientException:
        messages.error(request, _("Access denied."))
        return redirect('containerview')

    if request.method == 'POST':
        form = AddACLForm(request.POST)
        if form.is_valid():
            read_acl = meta.get('x-container-read', '')
            write_acl = meta.get('x-container-write', '')
            
            username = form.cleaned_data['username']
            
            # Handle project-wide access
            if form.cleaned_data['project_access']:
                project_id = username.split(':')[0]
                if form.cleaned_data['read']:
                    read_acl = f"{read_acl},{project_id}:*"
                if form.cleaned_data['write']:
                    write_acl = f"{write_acl},{project_id}:*"
            else:
                # Handle individual user access
                if form.cleaned_data['read']:
                    read_acl = f"{read_acl},{username}"
                if form.cleaned_data['write']:
                    write_acl = f"{write_acl},{username}"

            # Clean up ACLs
            read_acl = ','.join(filter(None, set(read_acl.split(','))))
            write_acl = ','.join(filter(None, set(write_acl.split(','))))

            headers = {
                'X-Container-Read': read_acl,
                'X-Container-Write': write_acl
            }

            try:
                client.post_container(storage_url, auth_token, container, headers)
                messages.success(request, _("ACL updated successfully."))
            except client.ClientException:
                messages.error(request, _("Failed to update ACL."))

    # Get current ACLs for display
    read_acls = meta.get('x-container-read', '').split(',')
    write_acls = meta.get('x-container-write', '').split(',')
    
    acls = {}
    for acl in set(read_acls + write_acls):
        if acl:
            acls[acl] = {
                'read': acl in read_acls,
                'write': acl in write_acls,
                'is_project': ':*' in acl
            }

    return render(request, 'edit_acl.html', {
        'container': container,
        'acls': acls,
        'form': AddACLForm(),
        'session': request.session
    })