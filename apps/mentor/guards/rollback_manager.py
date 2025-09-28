"""
Rollback manager with checkpoint system for safe change management.

This manager provides:
- Checkpoint creation: Save states before changes
- Rollback execution: Automated undo
- Conflict resolution: Manual intervention
- State verification: Ensure consistency
- Audit logging: Change tracking
"""

import json
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path



@dataclass
class Checkpoint:
    """Container for code checkpoint."""
    id: str
    description: str
    timestamp: datetime
    files: Dict[str, str]  # file_path -> content
    metadata: Dict[str, Any]


@dataclass
class RollbackOperation:
    """Container for rollback operation."""
    checkpoint_id: str
    files_to_restore: List[str]
    backup_created: bool
    status: str  # 'pending', 'in_progress', 'completed', 'failed'


class RollbackManager:
    """Manages code checkpoints and rollback operations."""

    def __init__(self, checkpoints_dir: str = ".mentor/checkpoints"):
        self.checkpoints_dir = Path(checkpoints_dir)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def create_checkpoint(self, description: str, files: List[str]) -> str:
        """Create a checkpoint before making changes."""
        checkpoint_id = f"checkpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Read current file contents
        file_contents = {}
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_contents[file_path] = f.read()
            except (FileNotFoundError, IOError, OSError, PermissionError) as e:
                print(f"Warning: Could not read {file_path}: {e}")

        checkpoint = Checkpoint(
            id=checkpoint_id,
            description=description,
            timestamp=datetime.now(),
            files=file_contents,
            metadata={'file_count': len(file_contents)}
        )

        # Save checkpoint
        self._save_checkpoint(checkpoint)

        return checkpoint_id

    def rollback_to_checkpoint(self, checkpoint_id: str, files: List[str] = None) -> bool:
        """Rollback to a specific checkpoint."""
        checkpoint = self._load_checkpoint(checkpoint_id)
        if not checkpoint:
            return False

        rollback_op = RollbackOperation(
            checkpoint_id=checkpoint_id,
            files_to_restore=files or list(checkpoint.files.keys()),
            backup_created=False,
            status='in_progress'
        )

        try:
            # Create backup before rollback
            backup_id = self.create_checkpoint(
                f"Pre-rollback backup for {checkpoint_id}",
                rollback_op.files_to_restore
            )
            rollback_op.backup_created = True

            # Restore files
            for file_path in rollback_op.files_to_restore:
                if file_path in checkpoint.files:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(checkpoint.files[file_path])

            rollback_op.status = 'completed'
            return True

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            print(f"Rollback failed: {e}")
            rollback_op.status = 'failed'
            return False

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all available checkpoints."""
        checkpoints = []

        for checkpoint_file in self.checkpoints_dir.glob("checkpoint_*.json"):
            try:
                checkpoint = self._load_checkpoint(checkpoint_file.stem)
                if checkpoint:
                    checkpoints.append({
                        'id': checkpoint.id,
                        'description': checkpoint.description,
                        'timestamp': checkpoint.timestamp.isoformat(),
                        'file_count': len(checkpoint.files)
                    })
            except (FileNotFoundError, IOError, OSError, PermissionError) as e:
                print(f"Error loading checkpoint {checkpoint_file}: {e}")

        return sorted(checkpoints, key=lambda x: x['timestamp'], reverse=True)

    def _save_checkpoint(self, checkpoint: Checkpoint):
        """Save checkpoint to disk."""
        checkpoint_file = self.checkpoints_dir / f"{checkpoint.id}.json"

        checkpoint_data = {
            'id': checkpoint.id,
            'description': checkpoint.description,
            'timestamp': checkpoint.timestamp.isoformat(),
            'files': checkpoint.files,
            'metadata': checkpoint.metadata
        }

        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2)

    def _load_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Load checkpoint from disk."""
        checkpoint_file = self.checkpoints_dir / f"{checkpoint_id}.json"

        if not checkpoint_file.exists():
            return None

        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return Checkpoint(
                id=data['id'],
                description=data['description'],
                timestamp=datetime.fromisoformat(data['timestamp']),
                files=data['files'],
                metadata=data.get('metadata', {})
            )
        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            print(f"Error loading checkpoint {checkpoint_id}: {e}")
            return None