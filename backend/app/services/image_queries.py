from sqlalchemy import Select, select

from app.models.image import Image
from app.models.user import User, UserRole


def apply_image_access_scope(
    query: Select,
    current_user: User,
    employee_id: str | None = None,
) -> Select:
    """为图片查询应用当前账号的可见范围与可选员工过滤。"""
    if current_user.role == UserRole.EMPLOYEE:
        return query.where(Image.owner_id == current_user.id)

    if current_user.role == UserRole.SUPERVISOR:
        accessible_owner_ids = select(User.id).where(
            (User.id == current_user.id)
            | (User.supervisor_id == current_user.id)
        )
        query = query.where(Image.owner_id.in_(accessible_owner_ids))

    if employee_id:
        query = query.where(Image.employee_id == employee_id)

    return query
