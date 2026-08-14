import sys
sys.path.insert(0, '/opt/channel-project/backend')
import os
os.chdir('/opt/channel-project/backend')
from app.database import SessionLocal
from app.models import Project, User
db = SessionLocal()
print('=== Users ===')
for u in db.query(User).all():
    print(f'id={u.id} username={u.username} real_name={u.real_name} role={u.role}')
print('=== Pending projects ===')
for p in db.query(Project).filter(Project.approval_status == 'pending_approval').all():
    approver = db.query(User).filter(User.id == p.approver_id).first() if p.approver_id else None
    print(f'id={p.id} name={p.project_name[:30]} approver_id={p.approver_id} approver={approver.real_name if approver else None}')