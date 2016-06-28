"""empty message

Revision ID: 0033_api_key_type
Revises: 0032_notification_created_status
Create Date: 2016-06-24 12:02:10.915817

"""

# revision identifiers, used by Alembic.
revision = '0033_api_key_type'
down_revision = '0032_notification_created_status'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('key_types',
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint('name')
    )
    op.add_column('api_keys', sa.Column('key_type', sa.String(length=255), nullable=True))
    op.add_column('api_keys_history', sa.Column('key_type', sa.String(length=255), nullable=True))
    op.add_column('notifications', sa.Column('api_key_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('notifications', sa.Column('key_type', sa.String(length=255), nullable=True))

    op.create_index(op.f('ix_api_keys_key_type'), 'api_keys', ['key_type'], unique=False)
    op.create_index(op.f('ix_api_keys_history_key_type'), 'api_keys_history', ['key_type'], unique=False)
    op.create_index(op.f('ix_notifications_api_key_id'), 'notifications', ['api_key_id'], unique=False)
    op.create_index(op.f('ix_notifications_key_type'), 'notifications', ['key_type'], unique=False)
    op.create_foreign_key(None, 'api_keys', 'key_types', ['key_type'], ['name'])
    op.create_foreign_key(None, 'notifications', 'api_keys', ['api_key_id'], ['id'])
    op.create_foreign_key(None, 'notifications', 'key_types', ['key_type'], ['name'])

    op.execute("insert into key_types values ('normal'), ('team')")
    op.execute("update api_keys set key_type = 'normal'")
    op.execute("update api_keys_history set key_type = 'normal'")

    op.alter_column('api_keys', 'key_type', nullable=False)
    op.alter_column('api_keys_history', 'key_type', nullable=False)
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('notifications_key_type_fkey', 'notifications', type_='foreignkey')
    op.drop_constraint('notifications_api_key_id_fkey', 'notifications', type_='foreignkey')
    op.drop_index(op.f('ix_notifications_key_type'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_api_key_id'), table_name='notifications')
    op.drop_column('notifications', 'key_type')
    op.drop_column('notifications', 'api_key_id')
    op.drop_index(op.f('ix_api_keys_history_key_type'), table_name='api_keys_history')
    op.drop_column('api_keys_history', 'key_type')
    op.drop_constraint('api_keys_key_type_fkey', 'api_keys', type_='foreignkey')
    op.drop_index(op.f('ix_api_keys_key_type'), table_name='api_keys')
    op.drop_column('api_keys', 'key_type')
    op.drop_table('key_types')
    ### end Alembic commands ###