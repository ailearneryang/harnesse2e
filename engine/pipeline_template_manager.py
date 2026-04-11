"""Pipeline template management for creating, editing, and organizing pipeline configurations."""

from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None


# Built-in template definitions
BUILTIN_TEMPLATES = [
    {
        "id": "default",
        "name": "完整流程",
        "description": "包含从需求分析到构建验证的完整 pipeline，适用于正式需求",
        "is_default": True,
        "is_builtin": True,
        "stages": [
            {"id": "intake", "name": "Request Intake", "agent": "planner"},
            {"id": "planning", "name": "Sprint Planning", "agent": "planner"},
            {"id": "software-requirement-orchestrator", "name": "Software Requirement Orchestrator", "agent": "software-requirement-orchestrator"},
            {"id": "cockpit-middleware-architect", "name": "Cockpit Middleware Architect", "agent": "cockpit-middleware-architect"},
            {"id": "development", "name": "Implementation", "agent": "developer"},
            {"id": "code_review", "name": "Code Review", "agent": "code-reviewer"},
            {"id": "security_review", "name": "Security Review", "agent": "security-reviewer"},
            {"id": "safety_review", "name": "Safety Review", "agent": "safety-reviewer"},
            {"id": "testing", "name": "QA Testing", "agent": "qa-engineer"},
            {"id": "delivery", "name": "Gerrit Delivery", "agent": "delivery-manager"},
            {"id": "build_verification", "name": "Build Verification", "agent": "build-verifier"},
        ],
    },
    {
        "id": "quick-dev",
        "name": "快速开发",
        "description": "跳过设计和安全审查，适用于小型代码修改或 bug 修复",
        "is_default": False,
        "is_builtin": True,
        "stages": [
            {"id": "intake", "name": "Request Intake", "agent": "planner"},
            {"id": "development", "name": "Implementation", "agent": "developer"},
            {"id": "code_review", "name": "Code Review", "agent": "code-reviewer"},
            {"id": "testing", "name": "QA Testing", "agent": "qa-engineer"},
        ],
    },
    {
        "id": "design-only",
        "name": "仅设计",
        "description": "只进行需求分析和架构设计，不进行开发实现",
        "is_default": False,
        "is_builtin": True,
        "stages": [
            {"id": "intake", "name": "Request Intake", "agent": "planner"},
            {"id": "planning", "name": "Sprint Planning", "agent": "planner"},
            {"id": "software-requirement-orchestrator", "name": "Software Requirement Orchestrator", "agent": "software-requirement-orchestrator"},
            {"id": "cockpit-middleware-architect", "name": "Cockpit Middleware Architect", "agent": "cockpit-middleware-architect"},
        ],
    },
    {
        "id": "cockpit-middleware",
        "name": "车载中间件流程",
        "description": "针对 IVI/座舱中间件的完整流程，包含安全审查",
        "is_default": False,
        "is_builtin": True,
        "stages": [
            {"id": "intake", "name": "Request Intake", "agent": "planner"},
            {"id": "planning", "name": "Sprint Planning", "agent": "planner"},
            {"id": "software-requirement-orchestrator", "name": "Software Requirement Orchestrator", "agent": "software-requirement-orchestrator"},
            {"id": "cockpit-middleware-architect", "name": "Cockpit Middleware Architect", "agent": "cockpit-middleware-architect"},
            {"id": "development", "name": "Implementation", "agent": "developer"},
            {"id": "code_review", "name": "Code Review", "agent": "code-reviewer"},
            {"id": "security_review", "name": "Security Review", "agent": "security-reviewer"},
            {"id": "safety_review", "name": "Safety Review", "agent": "safety-reviewer"},
            {"id": "testing", "name": "QA Testing", "agent": "qa-engineer"},
        ],
    },
]

# Available stages for validation
AVAILABLE_STAGES = {
    "intake": {"name": "Request Intake", "default_agent": "planner"},
    "planning": {"name": "Sprint Planning", "default_agent": "planner"},
    "requirements": {"name": "Requirements", "default_agent": "requirements-analyst"},
    "software-requirement-orchestrator": {"name": "Software Requirement Orchestrator", "default_agent": "software-requirement-orchestrator"},
    "design": {"name": "System Design", "default_agent": "system-architect"},
    "cockpit-middleware-architect": {"name": "Cockpit Middleware Architect", "default_agent": "cockpit-middleware-architect"},
    "development": {"name": "Implementation", "default_agent": "developer"},
    "code_review": {"name": "Code Review", "default_agent": "code-reviewer"},
    "security_review": {"name": "Security Review", "default_agent": "security-reviewer"},
    "safety_review": {"name": "Safety Review", "default_agent": "safety-reviewer"},
    "testing": {"name": "QA Testing", "default_agent": "qa-engineer"},
    "delivery": {"name": "Gerrit Delivery", "default_agent": "delivery-manager"},
    "build_verification": {"name": "Build Verification", "default_agent": "build-verifier"},
}


class PipelineTemplateManager:
    """Manages pipeline template CRUD operations with SQLite storage and YAML backup."""

    def __init__(self, harness_dir: str, state_store):
        self.harness_dir = harness_dir
        self.state_store = state_store
        self.templates_dir = os.path.join(harness_dir, "data", "pipeline_templates")
        self._lock = threading.RLock()
        os.makedirs(self.templates_dir, exist_ok=True)
        os.makedirs(os.path.join(self.templates_dir, "custom"), exist_ok=True)
        self._ensure_schema()
        self._ensure_builtin_templates()
        self._migrate_existing_pipeline()

    def _ensure_schema(self) -> None:
        """Create pipeline_templates table if not exists."""
        with self._lock:
            conn = self.state_store._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                # Check if table exists
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_templates'"
                )
                if not cursor.fetchone():
                    conn.execute(
                        """
                        CREATE TABLE pipeline_templates (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            description TEXT DEFAULT '',
                            stages TEXT NOT NULL,
                            is_default INTEGER DEFAULT 0,
                            is_builtin INTEGER DEFAULT 0,
                            created_by TEXT DEFAULT 'system',
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            usage_count INTEGER DEFAULT 0
                        )
                        """
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_pipeline_templates_default ON pipeline_templates(is_default)"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_pipeline_templates_builtin ON pipeline_templates(is_builtin)"
                    )
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()

    def _ensure_builtin_templates(self) -> None:
        """Insert or update builtin templates."""
        now = datetime.now().isoformat()
        with self._lock:
            conn = self.state_store._connect()
            try:
                for template in BUILTIN_TEMPLATES:
                    existing = conn.execute(
                        "SELECT id, usage_count FROM pipeline_templates WHERE id = ?",
                        (template["id"],),
                    ).fetchone()
                    
                    stages_json = json.dumps(template["stages"], ensure_ascii=False)
                    
                    if existing:
                        # Update builtin template but preserve usage_count
                        conn.execute(
                            """
                            UPDATE pipeline_templates SET
                                name = ?, description = ?, stages = ?,
                                is_default = ?, is_builtin = 1, updated_at = ?
                            WHERE id = ?
                            """,
                            (
                                template["name"],
                                template.get("description", ""),
                                stages_json,
                                1 if template.get("is_default") else 0,
                                now,
                                template["id"],
                            ),
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO pipeline_templates
                            (id, name, description, stages, is_default, is_builtin, created_by, created_at, updated_at, usage_count)
                            VALUES (?, ?, ?, ?, ?, 1, 'system', ?, ?, 0)
                            """,
                            (
                                template["id"],
                                template["name"],
                                template.get("description", ""),
                                stages_json,
                                1 if template.get("is_default") else 0,
                                now,
                                now,
                            ),
                        )
                    self._sync_to_file(template)
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()

    def _migrate_existing_pipeline(self) -> None:
        """Migrate existing custom_pipeline.yaml to template system."""
        custom_path = os.path.join(self.harness_dir, "data", "custom_pipeline.yaml")
        if not os.path.exists(custom_path) or yaml is None:
            return

        try:
            with open(custom_path, "r", encoding="utf-8") as f:
                custom = yaml.safe_load(f)
            
            if custom and custom.get("stages"):
                # Check if already migrated
                template_id = "migrated-custom"
                existing = self.get_template(template_id)
                if not existing:
                    self.create_template(
                        name="迁移的自定义流程",
                        stages=custom["stages"],
                        description="从 custom_pipeline.yaml 自动迁移",
                        template_id=template_id,
                    )
                # Backup and rename old file
                backup_path = custom_path + ".migrated"
                if not os.path.exists(backup_path):
                    shutil.move(custom_path, backup_path)
        except Exception:
            pass  # Silently ignore migration errors

    def _sync_to_file(self, template: Dict[str, Any]) -> None:
        """Sync template to YAML file for backup."""
        if yaml is None:
            return
        
        template_id = template["id"]
        if template.get("is_builtin"):
            file_path = os.path.join(self.templates_dir, f"{template_id}.yaml")
        else:
            file_path = os.path.join(self.templates_dir, "custom", f"{template_id}.yaml")
        
        # Prepare clean template for YAML
        yaml_data = {
            "id": template_id,
            "name": template.get("name"),
            "description": template.get("description", ""),
            "stages": template.get("stages", []),
            "is_default": template.get("is_default", False),
            "is_builtin": template.get("is_builtin", False),
        }
        
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f, allow_unicode=True, default_flow_style=False)

    def _generate_template_id(self) -> str:
        """Generate unique template ID."""
        return f"tpl-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"

    def _validate_stages(self, stages: List[Dict]) -> Tuple[bool, str]:
        """Validate stage configuration."""
        if not stages:
            return False, "At least one stage is required"
        
        if not isinstance(stages, list):
            return False, "stages must be a list"
        
        seen_ids = set()
        for i, stage in enumerate(stages):
            if not isinstance(stage, dict):
                return False, f"Stage {i} must be an object"
            
            stage_id = stage.get("id")
            if not stage_id:
                return False, f"Stage {i} missing 'id' field"
            
            if stage_id in seen_ids:
                return False, f"Duplicate stage id: {stage_id}"
            seen_ids.add(stage_id)
            
            # Validate stage_id is known (optional - allow custom stages)
            # if stage_id not in AVAILABLE_STAGES:
            #     return False, f"Unknown stage id: {stage_id}"
        
        return True, ""

    def list_templates(self, include_stages: bool = False) -> List[Dict[str, Any]]:
        """Get all templates with summary info."""
        with self._lock:
            conn = self.state_store._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT id, name, description, stages, is_default, is_builtin,
                           usage_count, created_at, updated_at
                    FROM pipeline_templates
                    ORDER BY is_default DESC, is_builtin DESC, usage_count DESC, name
                    """
                ).fetchall()
            finally:
                conn.close()

        templates = []
        default_id = None
        for row in rows:
            stages = json.loads(row["stages"])
            template = {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "is_default": bool(row["is_default"]),
                "is_builtin": bool(row["is_builtin"]),
                "stage_count": len(stages),
                "stage_ids": [s.get("id") for s in stages],
                "usage_count": row["usage_count"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            if include_stages:
                template["stages"] = stages
            templates.append(template)
            if row["is_default"]:
                default_id = row["id"]

        return {"templates": templates, "default_id": default_id}

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get single template by ID."""
        with self._lock:
            conn = self.state_store._connect()
            try:
                row = conn.execute(
                    """
                    SELECT id, name, description, stages, is_default, is_builtin,
                           created_by, usage_count, created_at, updated_at
                    FROM pipeline_templates WHERE id = ?
                    """,
                    (template_id,),
                ).fetchone()
            finally:
                conn.close()

        if not row:
            return None

        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "stages": json.loads(row["stages"]),
            "is_default": bool(row["is_default"]),
            "is_builtin": bool(row["is_builtin"]),
            "created_by": row["created_by"],
            "usage_count": row["usage_count"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create_template(
        self,
        name: str,
        stages: List[Dict],
        description: str = "",
        set_as_default: bool = False,
        created_by: str = "user",
        template_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new template."""
        if not name or not name.strip():
            raise ValueError("name is required")

        valid, error = self._validate_stages(stages)
        if not valid:
            raise ValueError(f"Invalid stages: {error}")

        template_id = template_id or self._generate_template_id()
        now = datetime.now().isoformat()
        stages_json = json.dumps(stages, ensure_ascii=False)

        with self._lock:
            conn = self.state_store._connect()
            try:
                # Check name uniqueness
                existing = conn.execute(
                    "SELECT id FROM pipeline_templates WHERE name = ?",
                    (name.strip(),),
                ).fetchone()
                if existing:
                    raise ValueError(f"Template name already exists: {name}")

                conn.execute("BEGIN IMMEDIATE")

                if set_as_default:
                    conn.execute("UPDATE pipeline_templates SET is_default = 0")

                conn.execute(
                    """
                    INSERT INTO pipeline_templates
                    (id, name, description, stages, is_default, is_builtin, created_by, created_at, updated_at, usage_count)
                    VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, 0)
                    """,
                    (template_id, name.strip(), description, stages_json, 1 if set_as_default else 0, created_by, now, now),
                )
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()

        template = {
            "id": template_id,
            "name": name.strip(),
            "description": description,
            "stages": stages,
            "is_default": set_as_default,
            "is_builtin": False,
        }
        self._sync_to_file(template)

        return {"id": template_id, "name": name.strip(), "message": "Template created successfully"}

    def update_template(self, template_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing template."""
        existing = self.get_template(template_id)
        if not existing:
            raise ValueError("Template not found")

        now = datetime.now().isoformat()
        allowed_fields = {"name", "description", "stages"}
        
        # For builtin templates, only allow name and description changes
        if existing["is_builtin"]:
            if "stages" in updates:
                raise ValueError("Cannot modify builtin template stages, only name and description")
            allowed_fields = {"name", "description"}

        update_parts = []
        params = []
        
        for field in allowed_fields:
            if field in updates:
                value = updates[field]
                if field == "stages":
                    valid, error = self._validate_stages(value)
                    if not valid:
                        raise ValueError(f"Invalid stages: {error}")
                    value = json.dumps(value, ensure_ascii=False)
                elif field == "name":
                    if not value or not value.strip():
                        raise ValueError("name cannot be empty")
                    value = value.strip()
                update_parts.append(f"{field} = ?")
                params.append(value)

        if not update_parts:
            raise ValueError("No valid fields to update")

        update_parts.append("updated_at = ?")
        params.append(now)
        params.append(template_id)

        with self._lock:
            conn = self.state_store._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                sql = f"UPDATE pipeline_templates SET {', '.join(update_parts)} WHERE id = ?"
                conn.execute(sql, tuple(params))
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()

        # Refresh and sync
        updated = self.get_template(template_id)
        if updated:
            self._sync_to_file(updated)

        return {"id": template_id, "message": "Template updated successfully"}

    def delete_template(self, template_id: str) -> Dict[str, Any]:
        """Delete a template with protection checks."""
        existing = self.get_template(template_id)
        if not existing:
            raise ValueError("Template not found")

        if existing["is_builtin"]:
            raise ValueError("Cannot delete builtin template")

        if existing["is_default"]:
            raise ValueError("Cannot delete the default template. Set another template as default first.")

        with self._lock:
            conn = self.state_store._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM pipeline_templates WHERE id = ?", (template_id,))
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()

        # Remove YAML backup
        file_path = os.path.join(self.templates_dir, "custom", f"{template_id}.yaml")
        if os.path.exists(file_path):
            os.remove(file_path)

        return {"id": template_id, "message": "Template deleted successfully"}

    def set_default_template(self, template_id: str) -> Dict[str, Any]:
        """Set a template as the default."""
        existing = self.get_template(template_id)
        if not existing:
            raise ValueError("Template not found")

        with self._lock:
            conn = self.state_store._connect()
            try:
                # Find current default
                current_default = conn.execute(
                    "SELECT id FROM pipeline_templates WHERE is_default = 1"
                ).fetchone()
                previous_default = current_default["id"] if current_default else None

                conn.execute("BEGIN IMMEDIATE")
                conn.execute("UPDATE pipeline_templates SET is_default = 0")
                conn.execute(
                    "UPDATE pipeline_templates SET is_default = 1, updated_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), template_id),
                )
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()

        # Sync files
        if previous_default:
            prev = self.get_template(previous_default)
            if prev:
                self._sync_to_file(prev)
        updated = self.get_template(template_id)
        if updated:
            self._sync_to_file(updated)

        return {
            "id": template_id,
            "message": "Template set as default",
            "previous_default": previous_default,
        }

    def get_default_template(self) -> Dict[str, Any]:
        """Get the current default template."""
        with self._lock:
            conn = self.state_store._connect()
            try:
                row = conn.execute(
                    """
                    SELECT id, name, description, stages, is_default, is_builtin,
                           created_by, usage_count, created_at, updated_at
                    FROM pipeline_templates WHERE is_default = 1 LIMIT 1
                    """
                ).fetchone()
            finally:
                conn.close()

        if row:
            return {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "stages": json.loads(row["stages"]),
                "is_default": True,
                "is_builtin": bool(row["is_builtin"]),
                "created_by": row["created_by"],
                "usage_count": row["usage_count"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

        # Fallback to "default" template
        return self.get_template("default") or BUILTIN_TEMPLATES[0]

    def resolve_template(self, template_id: Optional[str]) -> Dict[str, Any]:
        """Resolve template by ID, falling back to default if not found."""
        if template_id:
            template = self.get_template(template_id)
            if template:
                return template
        return self.get_default_template()

    def increment_usage(self, template_id: str) -> None:
        """Increment template usage count."""
        with self._lock:
            conn = self.state_store._connect()
            try:
                conn.execute(
                    "UPDATE pipeline_templates SET usage_count = usage_count + 1, updated_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), template_id),
                )
                conn.commit()
            except Exception:
                pass
            finally:
                conn.close()

    def get_preview(self, template_id: str, agents: Dict[str, Dict] = None) -> Optional[Dict[str, Any]]:
        """Get template preview data with agent info and connections."""
        template = self.get_template(template_id)
        if not template:
            return None

        agents = agents or {}
        stages = template["stages"]
        preview_stages = []
        
        for i, stage in enumerate(stages):
            stage_id = stage.get("id")
            agent_id = stage.get("agent", AVAILABLE_STAGES.get(stage_id, {}).get("default_agent", "unknown"))
            agent_info = agents.get(agent_id, {})
            
            preview_stages.append({
                "id": stage_id,
                "name": stage.get("name", AVAILABLE_STAGES.get(stage_id, {}).get("name", stage_id)),
                "agent": agent_id,
                "agent_name": agent_info.get("name", agent_id),
                "agent_model": agent_info.get("model", "unknown"),
                "position": i,
            })

        # Build connections
        connections = []
        for i in range(len(stages) - 1):
            connections.append({
                "from": stages[i].get("id"),
                "to": stages[i + 1].get("id"),
            })

        # Estimate duration (rough: 5 min per stage avg)
        estimated_duration = len(stages) * 5

        return {
            "id": template["id"],
            "name": template["name"],
            "description": template["description"],
            "stages": preview_stages,
            "connections": connections,
            "estimated_duration_minutes": estimated_duration,
            "stage_count": len(stages),
            "is_default": template["is_default"],
            "is_builtin": template["is_builtin"],
            "usage_count": template["usage_count"],
        }

    def get_available_stages(self) -> Dict[str, Dict]:
        """Return available stages for building templates."""
        return AVAILABLE_STAGES.copy()
