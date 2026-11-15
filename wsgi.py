"""Ponto de entrada WSGI para servidores de produção."""
import app

app.init()

from flask_app import flask_app as application
