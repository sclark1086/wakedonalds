from django.urls import path

from . import views

urlpatterns = [
    path("program/", views.rewards_program, name="rewards-program"),
]
