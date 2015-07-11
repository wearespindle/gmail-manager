from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.auth import views as auth_views

urlpatterns = [
    url(r'^accounts/login/$', auth_views.login, {'template_name': 'admin/login.html'}, name='login'),
    url(r'^admin/', include(admin.site.urls)),


    url(r'^gmailmanager/', include('gmailmanager.urls')),
]
