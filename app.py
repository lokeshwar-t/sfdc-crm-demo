import os
from flask import Flask
from flask_login import LoginManager, current_user
from config import Config
from database import db
from models import User, Notification, Role


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from routes.auth import auth_bp
    from routes.dashboards import dash_bp
    from routes.modules import mod_bp
    from routes.api import api_bp
    from routes.create import create_bp
    from routes.edit import edit_bp
    from routes.agent_api import agent_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(dash_bp)
    app.register_blueprint(mod_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(create_bp)
    app.register_blueprint(edit_bp)
    app.register_blueprint(agent_bp)

    @app.template_filter("money")
    def money(v):
        v = v or 0
        if abs(v) >= 1_000_000:
            return f"${v/1_000_000:,.1f}M"
        if abs(v) >= 1_000:
            return f"${v/1_000:,.0f}K"
        return f"${v:,.0f}"

    @app.template_filter("money_full")
    def money_full(v):
        return f"${(v or 0):,.0f}"

    @app.context_processor
    def inject_globals():
        unread = 0
        notifications = []
        if current_user.is_authenticated:
            notifications = (Notification.query.filter_by(user_id=current_user.id)
                             .order_by(Notification.created_at.desc()).limit(8).all())
            unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        roles = Role.query.filter(Role.slug != "employee").all()
        quick_accounts, quick_products = [], []
        if current_user.is_authenticated:
            from models import Account, Product
            quick_accounts = db.session.query(Account.id, Account.name).order_by(Account.name).all()
            quick_products = Product.query.all()
        return dict(company_name=app.config["COMPANY_NAME"], nav_notifications=notifications,
                    unread_count=unread, switchable_roles=roles,
                    quick_accounts=quick_accounts, quick_products=quick_products)

    with app.app_context():
        db_path = os.path.join(os.path.dirname(__file__), "crm_demo.db")
        fresh = not os.path.exists(db_path)
        db.create_all()  # idempotent — also creates agent_runs/agent_drafts on an existing db
        if fresh:
            from seed_data import seed
            seed()
        _ensure_agent_user(app)

    return app


def _ensure_agent_user(app):
    """Seed the agent service account that every agent write is attributed to."""
    if User.query.filter_by(email=app.config["AGENT_EMAIL"]).first():
        return
    ops_role = Role.query.filter_by(slug="salesops").first()
    agent = User(name="CloudVision Agent", email=app.config["AGENT_EMAIL"],
                 title="Autonomous Agent", avatar_color="#0B7C86",
                 role_id=ops_role.id if ops_role else None)
    db.session.add(agent)
    db.session.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5050)
