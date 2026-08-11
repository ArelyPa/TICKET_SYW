from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from backend.domain.entities.resource import Skill

# ── Catálogos fijos (CHECKs en DB) ─────────────────────────────────────

STATUSES = (
    "nuevo", "pre_analisis", "contacto", "en_analisis", "en_ejecucion",
    "en_pruebas", "pendiente_usuario", "resuelto", "cerrado", "cancelado",
)
FINAL_STATUSES = ("cerrado", "cancelado")
TICKET_TYPES = ("incident", "evolutive", "preventive")
PRIORITIES = ("critical", "high", "medium", "low")
SEVERITIES = ("s1", "s2", "s3", "s4")
ESCALATION_LEVELS = ("n1", "n2", "n3", "n4")

STATUS_LABELS = {
    "nuevo": "Nuevo", "pre_analisis": "Pre-Análisis", "contacto": "Contacto",
    "en_analisis": "En Análisis", "en_ejecucion": "En Ejecución",
    "en_pruebas": "En Pruebas", "pendiente_usuario": "Pendiente de Usuario",
    "resuelto": "Resuelto", "cerrado": "Cerrado", "cancelado": "Cancelado",
}

# Bloqueo de campos por estado (FR-010) — única fuente de verdad.
# Campos listados = NO editables via PATCH mientras el ticket esté en ese estado.
_BASE_LOCKED = {"status", "ticket_number", "record_type_id", "created_by"}
FIELD_LOCKS: dict[str, set[str]] = {
    "nuevo": set(),
    "pre_analisis": set(),
    "contacto": {"estimated_resolution_minutes", "severity", "priority"},
    "en_analisis": set(),  # se desbloquean tiempo estimado, severidad y prioridad
    "en_ejecucion": {"estimated_resolution_minutes"},
    "en_pruebas": {"estimated_resolution_minutes"},
    "pendiente_usuario": {"estimated_resolution_minutes", "severity", "priority"},
    "resuelto": {"estimated_resolution_minutes", "severity", "priority"},
    "cerrado": {"title", "description", "ticket_type", "priority", "severity",
                "escalation_level", "estimated_resolution_minutes", "client_contact_id",
                "list_id", "related_ticket_id"},
    "cancelado": {"title", "description", "ticket_type", "priority", "severity",
                  "escalation_level", "estimated_resolution_minutes", "client_contact_id",
                  "list_id", "related_ticket_id"},
}


def locked_fields_for(status: str) -> list[str]:
    return sorted(_BASE_LOCKED | FIELD_LOCKS.get(status, set()))


def format_ticket_number(n: int) -> str:
    return f"TK-{n:06d}"


@dataclass
class Ticket:
    id: uuid.UUID
    ticket_number: int
    title: str
    description: str
    ticket_type: str
    priority: str
    severity: str
    client_id: uuid.UUID
    created_by: uuid.UUID
    record_type_id: Optional[uuid.UUID] = None
    status: str = "nuevo"
    escalation_level: str = "n2"
    project_id: Optional[uuid.UUID] = None
    tool_id: Optional[uuid.UUID] = None
    process_id: Optional[uuid.UUID] = None
    assignee_id: Optional[uuid.UUID] = None
    client_contact_id: Optional[uuid.UUID] = None
    estimated_resolution_minutes: Optional[int] = None
    resolution_type_id: Optional[uuid.UUID] = None
    related_ticket_id: Optional[uuid.UUID] = None
    list_name: Optional[str] = None
    list_id: Optional[uuid.UUID] = None
    parent_task_id: Optional[uuid.UUID] = None
    resolved_at: Optional[datetime] = None
    resolution_accepted_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    skills: list[Skill] = field(default_factory=list)
    # SLA (Fase 4, spec 014) — snapshot de consumo de la fase de SLA vigente. Solo se calcula
    # para record_type "Ticket" (FR-012); en Tareas/Subtareas quedan en None.
    sla_rule_id: Optional[uuid.UUID] = None
    sla_phase: Optional[str] = None
    sla_phase_limit_minutes: Optional[int] = None
    sla_consumed_seconds: int = 0
    sla_last_resume_at: Optional[datetime] = None
    sla_status: str = "sin_sla"
    sla_contact_result: Optional[str] = None
    sla_contact_consumed_seconds: Optional[int] = None
    # OBS-0059 (spec 033): análogo a Contacto, pero para la fase de Ejecución/cierre —
    # se congela al cerrar/resolver/cancelar el ticket si esa fase llegó a correr.
    sla_execution_result: Optional[str] = None
    sla_execution_consumed_seconds: Optional[int] = None
    # Trazabilidad de origen externo (spec 041): poblados solo cuando el Ticket/Tarea proviene
    # de una importación de Teamwork.
    external_reference_id: Optional[str] = None
    external_reference_url: Optional[str] = None

    @property
    def number_display(self) -> str:
        return format_ticket_number(self.ticket_number)

    @property
    def is_final(self) -> bool:
        return self.status in FINAL_STATUSES

    def locked_fields(self) -> list[str]:
        return locked_fields_for(self.status)
