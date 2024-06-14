#!/usr/bin/env python

import os
from app import app, db, Admins

if 'migrations' not in os.listdir('.'):
    os.system('flask db init')
    os.system('flask db migrate -m "Initial migration."')
    os.system('flask db upgrade')

    with app.app_context():
        default_admin = Admins()
        default_admin.username = 'admin'
        default_admin.password = '12345'
        
        db.session.add(default_admin)
        db.session.commit()
        
        print('admin account created with 12345 as the default password')
        
else:
    print('admin account default password is already created')
