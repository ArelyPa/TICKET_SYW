from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from backend.infra.models.role_model import RoleModel, PermissionModel  # noqa: E402, F401
from backend.infra.models.user_model import UserModel  # noqa: E402, F401
from backend.infra.models.client_model import ClientModel  # noqa: E402, F401
from backend.infra.models.project_model import ProjectModel  # noqa: E402, F401
from backend.infra.models.resource_model import SkillModel, ResourceModel  # noqa: E402, F401
from backend.infra.models.client_contact_model import ClientContactModel  # noqa: E402, F401
from backend.infra.models.sla_rule_model import SlaRuleModel  # noqa: E402, F401
import backend.infra.models.catalog_model  # noqa: E402, F401
import backend.infra.models.task_list_model  # noqa: E402, F401
import backend.infra.models.ticket_model  # noqa: E402, F401
import backend.infra.models.comment_model  # noqa: E402, F401
import backend.infra.models.notification_model  # noqa: E402, F401
import backend.infra.models.project_member_model  # noqa: E402, F401
import backend.infra.models.ticket_timer_model  # noqa: E402, F401
import backend.infra.models.work_session_model  # noqa: E402, F401
import backend.infra.models.calendar_model  # noqa: E402, F401
import backend.infra.models.report_view_model  # noqa: E402, F401
import backend.infra.models.teamwork_integration_model  # noqa: E402, F401
