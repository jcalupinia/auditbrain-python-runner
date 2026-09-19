"""Adaptador Command Center: JWT + proyecto; procesamiento sin persistir evidencia."""
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from backend.app.auth.deps import require_staff
from backend.app.db.session import get_db
from backend.app.context.models import Project, Client
from backend.app.context.service import user_can_access_project
from .engine import calculate
from .exports import build_xlsx, build_html, schedules
from .metadata import REFERENCES
from .parsers import extract, MAX_BYTES

router=APIRouter(prefix='/aud/inventarios-vnr',tags=['aud-inventarios-vnr'])


def access(project_id:int,user=Depends(require_staff),db:Session=Depends(get_db)):
    project=db.get(Project,project_id)
    if not project or not project.is_active or not user_can_access_project(db,user,project):
        raise HTTPException(403,'Sin acceso al proyecto.')
    return project,user,db


async def bounded_body(request,limit):
    data=bytearray()
    async for chunk in request.stream():
        if len(data)+len(chunk)>limit:raise HTTPException(413,'Solicitud supera el tamaño permitido.')
        data.extend(chunk)
    return bytes(data)


async def request_data(request):
    try:
        data=json.loads(await bounded_body(request,4*1024*1024))
        if not isinstance(data,dict):raise ValueError()
        return data
    except (ValueError,UnicodeError):raise HTTPException(400,'Solicitud JSON no válida.') from None


def safe_calculate(data):
    try:return calculate(data)
    except (ValueError,TypeError,KeyError,AttributeError) as exc:raise HTTPException(422,str(exc)) from None


@router.get('/{project_id}/context')
def context(project_id:int,authorized=Depends(access)):
    project,user,db=authorized
    client=db.get(Client,project.client_id)
    return {'client':client.name if client else '', 'year':project.period_end.year if project.period_end else '', 'cutoff':project.period_end.isoformat() if project.period_end else '', 'preparer':getattr(user,'display_name',None) or getattr(user,'full_name',None) or user.email,'references':REFERENCES}


@router.post('/{project_id}/extract')
async def extraction(project_id:int,request:Request,filename:str=Query(...,max_length=200),authorized=Depends(access)):
    data=await bounded_body(request,MAX_BYTES)
    try:return await run_in_threadpool(extract,filename,data)
    except ValueError as exc:raise HTTPException(422,str(exc)) from None


@router.post('/{project_id}/process')
async def process(project_id:int,request:Request,authorized=Depends(access)):
    result=await run_in_threadpool(safe_calculate,await request_data(request))
    return {**result,'schedules':schedules(result)}


@router.post('/{project_id}/download')
async def download(project_id:int,request:Request,format:str=Query(...,pattern='^(xlsx|html)$'),authorized=Depends(access)):
    result=await run_in_threadpool(safe_calculate,await request_data(request))
    if format=='xlsx':
        content=await run_in_threadpool(build_xlsx,result);mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:content=await run_in_threadpool(build_html,result);mime='text/html; charset=utf-8'
    return Response(content,media_type=mime,headers={'Content-Disposition':f'attachment; filename="AuditBrain_VNR.{format}"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
