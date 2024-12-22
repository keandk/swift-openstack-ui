"""
URL configuration for swiftproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from swiftapp.views import (
    containerview, objectview, download, delete_object, login, 
    tempurl, upload, create_pseudofolder, create_container, 
    delete_container, public_objectview, toggle_public, edit_acl
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', login, name="login"),
    path('', containerview, name="containerview"),
    path('public/<str:account>/<str:container>/<path:prefix>/', 
         public_objectview, name="public_objectview"),
    path('public/<str:account>/<str:container>/',
         public_objectview, name="public_objectview"),
    path('toggle_public/<str:container>/',
         toggle_public, name="toggle_public"),
    path('tempurl/<str:container>/<path:objectname>/',
         tempurl, name="tempurl"),
    path('upload/<str:container>/<path:prefix>/',
         upload, name="upload"),
    path('upload/<str:container>/',
         upload, name="upload"),
    path('create_pseudofolder/<str:container>/<path:prefix>/',
         create_pseudofolder, name="create_pseudofolder"),
    path('create_pseudofolder/<str:container>/',
         create_pseudofolder, name="create_pseudofolder"),
    path('create_container/',
         create_container, name="create_container"),
    path('delete_container/<str:container>/',
         delete_container, name="delete_container"),
    path('download/<str:container>/<path:objectname>/',
         download, name="download"),
    path('delete/<str:container>/<path:objectname>/',
         delete_object, name="delete_object"),
    path('objects/<str:container>/<path:prefix>/',
         objectview, name="objectview"),
    path('objects/<str:container>/',
         objectview, name="objectview"),
    path('acls/<str:container>/',
         edit_acl, name="edit_acl"),
]
