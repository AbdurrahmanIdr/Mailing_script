#!/usr/bin/env python3

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
    os.system('flask db migrate -m "db update"')
    os.system('flask db upgrade')
    print('admin account default password is already created')
    print('db migrated successfully.')
