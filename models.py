from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False) # MASTER, GESTOR, LOJISTA
    parent_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationships
    children = db.relationship('User', backref=db.backref('parent', remote_side=[id]))
    # Note: client_config relationship is defined in ClientConfig with foreign_keys

class ClientConfig(db.Model):
    """Multi-Tenant Client Configuration - Each client has independent credentials"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Client Business Information
    name = db.Column(db.String(200), nullable=False)  # Nome do negócio
    whatsapp_number = db.Column(db.String(20), nullable=True)  # Número WhatsApp
    
    # Facebook/Meta Credentials (REQUIRED for multi-tenant)
    fb_access_token = db.Column(db.String(500), nullable=False)  # Token próprio do cliente
    ad_account_id = db.Column(db.String(100), nullable=False)  # act_xxxxx
    pixel_id = db.Column(db.String(100), nullable=False)  # Para CAPI
    
    # Multi-Tenant Isolation
    gestor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Gestor que criou
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Lojista associado
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships with explicit foreign_keys
    gestor = db.relationship('User', foreign_keys=[gestor_id], backref='managed_clients')
    lojista = db.relationship('User', foreign_keys=[user_id], backref='client_config')

class Lead(db.Model):
    short_id = db.Column(db.Integer, primary_key=True)
    fbclid = db.Column(db.String(500))
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='CLICKED') # CLICKED, HOT, SOLD, ARCHIVED
    sale_value = db.Column(db.Float, nullable=True)
    
    # Link lead to a specific client (Lojista)
    # For MVP, we might need to know WHICH client this lead belongs to.
    # We can infer from the ad link parameters or store client_id.
    # Let's add client_id to be safe for multi-tenant.
    client_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
