from sqlalchemy import CheckConstraint,Column,Float,ForeignKey,Integer,JSON,String,Table
from core.db import metadata

findings = Table(
    "feedback_findings",metadata,
    Column("code",String(24),primary_key=True),
    Column("focus_window",String(24),ForeignKey("sound_windows.code"),nullable=False,unique=True),
    Column("category",String(16),nullable=False),
    Column("score",Float,nullable=False),
    Column("neighbors",Integer,nullable=False),
    Column("shared_points",JSON,nullable=False),
    Column("reviewed_by",String(80),nullable=False),
    Column("compute_token",String(32),nullable=False,unique=True),
    # 签入时固化的用样依据：basis 为基线样本编号，basis_detail 为完整取样快照。
    # 旧记录两列均为 NULL，核实时标记为无法核实。
    Column("basis",JSON),
    Column("basis_detail",JSON),
    CheckConstraint("category IN ('local','coordinated','normal')"),
)

tickets = Table(
    "channel_tickets",metadata,
    Column("code",String(24),primary_key=True),
    Column("point",String(20),ForeignKey("microphone_points.code"),nullable=False),
    Column("finding",String(24),ForeignKey("feedback_findings.code"),nullable=False,unique=True),
    Column("old_channel",String(12),nullable=False),
    Column("new_channel",String(12),nullable=False),
    Column("reline_window",String(24),ForeignKey("sound_windows.code"),unique=True),
    Column("test_score",Float),
    Column("test_basis",JSON),
    Column("state",String(16),nullable=False),
    Column("isolated_by",String(80),nullable=False),
    Column("restored_by",String(80)),
    CheckConstraint("old_channel <> new_channel"),
    CheckConstraint("state IN ('isolated','restored')"),
)
