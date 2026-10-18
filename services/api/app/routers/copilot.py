"""RM copilot and AI quality analyst endpoints. Read-only preparation; every action stays with a person."""
import os,time
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import CurrentUser,get_current_user
from ..schemas.rm import RMCopilotContext,RMCopilotRequest,RMCopilotTurn
from ..services.rm import record_ai_audit_event
from ..services.assistant.engine import ProviderUnavailable,ProviderFailure
from ..services.assistant import copilot
router=APIRouter(prefix='/v1/rm',tags=['staff-assistants'])

def rm_scope(db,user,party_id):
    return copilot.party_scope(db,user,party_id) if party_id else copilot.book_scope(db,user)

def respond(db,user,surface,scope,req):
    version=copilot.PROMPT_COPILOT_VERSION if surface=='RM' else copilot.PROMPT_QUALITY_VERSION
    resource_type={'PARTY':'PARTY','BOOK':'RM_BOOK','QUALITY':'QUALITY'}[scope['scope']]
    started=time.perf_counter()
    def failed(status,exc):
        record_ai_audit_event(db,user,'AI_COPILOT_FAILED',resource_type,scope['resource'],'LIVE',os.getenv('GEMINI_MODEL','vertex'),version,max(1,int((time.perf_counter()-started)*1000)),[]);db.commit()
        message=str(exc) or 'Google response was unavailable, timed out or failed validation.'
        if 'no simulated fallback' not in message.lower():message+=' No simulated fallback was used.'
        raise HTTPException(status,message)
    try:turn=copilot.answer(surface,scope,req.message,req.history)
    except ProviderUnavailable as exc:failed(503,exc)
    except ProviderFailure as exc:failed(502,exc)
    except HTTPException:raise
    except Exception as exc:failed(502,ProviderFailure('Google response was unavailable, timed out or failed validation.'))
    record_ai_audit_event(db,user,'AI_COPILOT_ANSWERED',resource_type,scope['resource'],turn['mode'],turn['model'],version,turn['latency_ms'],[r['id'] for r in turn['refs']]);db.commit()
    return turn

def check_version(scope,base_version,what):
    if scope['base_version'] is None:return
    if base_version is None:raise HTTPException(422,f'Send the {what} version you are viewing.')
    if base_version!=scope['base_version']:raise HTTPException(409,f'This {what} changed since you opened it. Reload to see the current version before asking.')

@router.get('/copilot/context',response_model=RMCopilotContext)
def copilot_context(party_id:str|None=None,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    return copilot.context_data('RM',rm_scope(db,user,party_id))

@router.post('/copilot/turns',response_model=RMCopilotTurn)
def copilot_turn(req:RMCopilotRequest,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    if req.run_id:raise HTTPException(422,'Evaluation runs belong to the AI quality analyst.')
    scope=rm_scope(db,user,req.party_id);check_version(scope,req.base_version,'relationship')
    return respond(db,user,'RM',scope,req)

@router.get('/quality-assistant/context',response_model=RMCopilotContext)
def quality_context(run_id:str|None=None,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    return copilot.context_data('QUALITY',copilot.quality_scope(db,user,run_id))

@router.post('/quality-assistant/turns',response_model=RMCopilotTurn)
def quality_turn(req:RMCopilotRequest,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    if req.party_id:raise HTTPException(422,'Customer relationships belong to the RM copilot.')
    scope=copilot.quality_scope(db,user,req.run_id);check_version(scope,req.base_version,'evaluation run')
    return respond(db,user,'QUALITY',scope,req)
