from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from database import db
from models import User, Role, AuditLog

auth_bp = Blueprint("auth", __name__)

DEMO_LOGINS = [
    ("ceo@cloudvision.com", "CEO", "Alexandra Reyes"),
    ("vpsales@cloudvision.com", "VP Sales", "Marcus Webb"),
    ("rep@cloudvision.com", "Sales Rep", "Jordan Ellis"),
    ("csm@cloudvision.com", "Customer Success", "Sophia Laurent"),
    ("finance@cloudvision.com", "Finance", "Daniel Osei"),
    ("salesops@cloudvision.com", "Sales Ops", "Rachel Kim"),
    ("ea@cloudvision.com", "Exec Assistant", "Taylor Morgan"),
]


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dash.home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and request.form.get("password") == user.password:
            login_user(user)
            db.session.add(AuditLog(user_id=user.id, action="Logged in", entity="user", entity_id=user.id))
            db.session.commit()
            return redirect(url_for("dash.home"))
        flash("Invalid credentials. Use any demo account with password demo123.", "danger")
    return render_template("login.html", demo_logins=DEMO_LOGINS)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/switch-role/<slug>")
@login_required
def switch_role(slug):
    role = Role.query.filter_by(slug=slug).first()
    if role:
        current_user.active_role_slug = slug
        db.session.add(AuditLog(user_id=current_user.id, action=f"Switched view to {role.name}",
                                entity="role", entity_id=role.id))
        db.session.commit()
        flash(f"Now viewing as {role.name}", "success")
    return redirect(url_for("dash.home"))
