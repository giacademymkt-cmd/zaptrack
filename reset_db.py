#!/usr/bin/env python3
"""
Reset database and create test users with Facebook config
"""
import os
from app import app, db
from models import User, ClientConfig
from werkzeug.security import generate_password_hash

with app.app_context():
    # Drop all tables and recreate
    db.drop_all()
    db.create_all()
    print("✅ Database recreated!")
    
    # Create MASTER user
    master = User(
        username='admin',
        password_hash=generate_password_hash('admin123', method='pbkdf2:sha256'),
        role='MASTER'
    )
    db.session.add(master)
    db.session.commit()
    print("✅ Admin user created (admin/admin123)")
    
    # Create GESTOR user
    gestor = User(
        username='gestor',
        password_hash=generate_password_hash('gestor123', method='pbkdf2:sha256'),
        role='GESTOR',
        parent_id=master.id
    )
    db.session.add(gestor)
    db.session.commit()
    print("✅ Gestor user created (gestor/gestor123)")
    
    # Create LOJISTA user (client)
    lojista = User(
        username='hellwig',
        password_hash=generate_password_hash('hellwig123', method='pbkdf2:sha256'),
        role='LOJISTA',
        parent_id=gestor.id
    )
    db.session.add(lojista)
    db.session.commit()
    print("✅ Client user created (hellwig/hellwig123)")
    
    # Create Facebook config for client
    try:
        import toml
        secrets = toml.load('.streamlit/secrets.toml')
        fb_token = secrets.get('FB_ACCESS_TOKEN', 'PLACEHOLDER_TOKEN')
        ad_account = secrets.get('AD_ACCOUNT_ID', 'PLACEHOLDER_ACCOUNT')
        pixel_id = secrets.get('PIXEL_ID', '123456789')
    except:
        fb_token = 'PLACEHOLDER_TOKEN'
        ad_account = 'PLACEHOLDER_ACCOUNT'
        pixel_id = '123456789'
    
    config = ClientConfig(
        user_id=lojista.id,
        gestor_id=gestor.id,
        name='Hellwig Campaign',
        fb_access_token=fb_token,
        ad_account_id=ad_account,
        pixel_id=pixel_id
    )
    db.session.add(config)
    db.session.commit()
    print("✅ Facebook config created for client")
    
    print("\n" + "="*50)
    print("DATABASE SETUP COMPLETE!")
    print("="*50)
    print("\nLogin credentials:")
    print("  Admin:  admin / admin123")
    print("  Gestor: gestor / gestor123")
    print("  Client: hellwig / hellwig123")
    print("\nRestart the Flask app and try logging in!")
