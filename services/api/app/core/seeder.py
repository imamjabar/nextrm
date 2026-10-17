from sqlalchemy.orm import Session
from ..models.entities import (
    InstitutionModel,
    UserAssignmentModel,
)

def seed_demo_database(db: Session):
    """
    Populates the database with initial synthetic bank fixtures if not already present.
    """
    if not db.query(InstitutionModel).filter(InstitutionModel.id == "demo-bank").first():
        db.add(
            InstitutionModel(
                id="demo-bank",
                name="Nusantara Finance",
                institution_type="BANK",
                policy_pack_id="policy-bank-default",
                approval_mode="SANDBOX_LOCAL"
            )
        )
        db.commit()

    if not db.query(UserAssignmentModel).filter(UserAssignmentModel.id == "ua-maya").first():
        db.add(
            UserAssignmentModel(
                id="ua-maya",
                user_id="usr-maya",
                name="Maya Putri",
                email="maya.putri@nusantarafinance.co.id",
                role="RM",
                tenant_id="demo-bank"
            )
        )
        db.commit()

    from ..services.rm_seed import seed_relationships
    seed_relationships(db)

    from ..services.bank_seed import seed_bank_data
    for inst in db.query(InstitutionModel).filter_by(institution_type="BANK").all():
        seed_bank_data(db, inst.id)
