"""Institution-owned static menu links; never model-selected URLs or financial tools."""
import os,json
from urllib.parse import urlsplit
from fastapi import HTTPException
MENUS=[('savings','Savings','Products → Savings'),('deposit','Term deposits','Products → Deposits'),('loan','Loans','Products → Loans'),('cards','Card service','Help → Cards'),('payments','Payment help','Help → Transfers'),('merchant','Business payment services','Business → Payment services')]
def destination_data(tenant):
    try:config=json.loads(os.getenv('NEXTRM_MENU_LINKS_JSON','{}'))
    except (ValueError,TypeError):raise HTTPException(503,'Institution menu configuration is invalid.')
    links=config.get(tenant,{}) if isinstance(config,dict) else None
    if not isinstance(links,dict):raise HTTPException(503,'Institution menu configuration is invalid.')
    out=[]
    for key,title,path in MENUS:
        url=links.get(key);status='NOT_CONFIGURED'
        if url:
            if not isinstance(url,str):raise HTTPException(503,'Institution menu link is invalid.')
            try:parsed=urlsplit(url)
            except ValueError:raise HTTPException(503,'Institution menu link is malformed.')
            local=os.getenv('ENVIRONMENT','development')!='production' and parsed.scheme=='http' and parsed.hostname in {'localhost','127.0.0.1'}
            if not parsed.hostname or parsed.username or parsed.password or any(ord(c)<32 for c in url) or not (parsed.scheme=='https' or local):
                raise HTTPException(503,'Institution menu link must be an approved HTTPS destination.')
            status='READY'
        out.append({'key':key,'title':title,'menu_path':path,'href':url or None,'status':status,'boundary':'Continues in the bank’s separate menu. NextRM does not submit an application, open a product, approve a loan or reconcile a transaction.'})
    return {'destinations':out}
