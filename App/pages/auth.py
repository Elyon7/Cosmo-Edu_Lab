import os
import io
import json
import nicegui
from nicegui import ui, app, run , client

import datetime


#from nicegui_toolkit import inject_layout_tool


from core import app_data, save_data, BASE_DIR, DATA_DIR
from layout import aria_input, aria_button, accessible_notify


def create_auth_routes():
    @ui.page('/login')
    def login_page():
        ui.run_javascript("setTimeout(() => document.querySelector('h1, .title, .text-2xl')?.focus(), 3600)")
        """Login page for users."""
        def try_login():
            if app_data['users'].get(username.value) == password.value:
                app.storage.user['name'] = username.value
                ui.navigate.to('/main')
            else:
                accessible_notify('Invalid username or password', type_='warning')

        with ui.card().classes('absolute-center'):
            ui.label('Login').classes('text-2xl font-bold').props('role=heading aria-level=2 aria-label=Login form area tabindex=0')
            username = aria_input('Username',"Insert the username").on('keydown.enter', lambda: password.focus())
            password = aria_input('Password',"Insert the password", password=True).on('keydown.enter', try_login)
            aria_button('Login', "Log in", on_click=try_login)
            ui.link("Don't have an account? Register", '/register').classes('mt-2')

    @ui.page('/register')
    def register_page():
        """Registration page for new users."""
        def do_register():
            if not new_user.value or not new_pass.value:
                accessible_notify('Username and password are required.', type_='warning')
                return
            if new_user.value in app_data['users']:
                accessible_notify('This username is already taken.', type_='warning')
                return
            app_data['users'][new_user.value] = new_pass.value
            save_data()
            accessible_notify('User registered! You can now log in.', type_='success')
            ui.navigate.to('/login')

        with ui.card().classes('absolute-center'):
            ui.label('Register New Account').classes('text-2xl font-bold').props('role=heading aria-level=2 tabindex=0')
            new_user = aria_input('New Username', "Insert the new username")
            new_pass = aria_input('New Password',"Insert the new password", password=True)
            aria_button('Register', "Create a new account", on_click=do_register)

    @ui.page('/')
    def index_page():
        """Redirects to login or main menu based on authentication status."""
        if not app.storage.user.get('name'):
            ui.navigate.to('/login')
        else:
            ui.navigate.to('/main')