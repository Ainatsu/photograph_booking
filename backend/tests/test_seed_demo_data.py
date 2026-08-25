from backend.app.core.security import verify_password
from backend.app.models.order import Order
from backend.app.models.project import ShootProject
from backend.app.models.user import User
from backend.scripts.seed_demo_data import DEMO_USERS, PASSWORD, seed_demo_data


def test_demo_seed_is_idempotent_and_accounts_are_login_ready(db):
    first = seed_demo_data(db)
    second = seed_demo_data(db)

    assert first == second == {"users": 5, "projects": 3, "orders": 1, "assets": 12}
    assert db.query(User).filter(User.email.like("%.demo@example.com")).count() == 5
    assert db.query(ShootProject).filter(ShootProject.title.in_([
        "夏日城市人像企划", "复古婚礼纪实", "棚拍风格招募",
    ])).count() == 3
    assert db.query(Order).filter_by(source_id="demo-order-1").count() == 1

    for email, _display_name, _role in DEMO_USERS.values():
        user = db.query(User).filter_by(email=email).one()
        assert verify_password(PASSWORD, user.hashed_password)
