"""
权限模块
简化版权限管理：管理员模式 / 查询模式
"""
import config


def verify_password(password: str) -> dict:
    """
    验证密码
    返回: {"success": True/False, "role": "admin"/"query", "message": "..."}
    """
    if password == config.ADMIN_PASSWORD:
        return {"success": True, "role": "admin", "message": "管理员登录成功"}
    elif password == config.QUERY_PASSWORD:
        return {"success": True, "role": "query", "message": "查询模式登录成功"}
    return {"success": False, "role": "", "message": "密码错误"}


def can_edit(role: str) -> bool:
    """检查角色是否有编辑权限"""
    return role == "admin"


def can_query_secret(role: str) -> bool:
    """检查角色是否有密码查询权限"""
    return role == "admin"
