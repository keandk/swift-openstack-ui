""" Forms for swiftbrowser.browser """
# -*- coding: utf-8 -*-
from django import forms


class CreateContainerForm(forms.Form):
    """ Simple form for container creation """
    containername = forms.CharField(max_length=100)


class AddACLForm(forms.Form):
    """Form for ACLs with Keystone support"""
    username = forms.CharField(max_length=100, 
                             help_text="Format: project_id:user_id for Keystone auth")
    read = forms.BooleanField(required=False)
    write = forms.BooleanField(required=False)
    project_access = forms.BooleanField(required=False, 
                                      help_text="Grant access to entire project")


class PseudoFolderForm(forms.Form):
    """ Upload form """
    foldername = forms.CharField(max_length=100)


class LoginForm(forms.Form):
    """ Login form """
    username = forms.CharField(max_length=100)
    password = forms.CharField(widget=forms.PasswordInput)
