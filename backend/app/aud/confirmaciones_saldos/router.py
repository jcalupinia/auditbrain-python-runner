"""Adaptador Command Center: JWT + proyecto; prepara la circularización sin persistir evidencia.

El envío lo dispara el auditor: `/enviar` usa el mismo servicio de correo de la
plataforma (Resend, `notifications.email.send_email`) que ya manda usuario y clave a
los clientes. Las respuestas se dirigen al correo del auditor (reply-to).
"""
import json
import re
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from backend.app.auth.deps import require_staff
from backend.app.db.session import get_db
from backend.app.context.models import Project, Client
from backend.app.context.service import user_can_access_project
from backend.app.notifications.email import send_email
from .engine import calculate
from .exports import (build_xlsx, build_html, build_docx, build_pdf, PDFNoDisponible,
                      schedules, letter_email_html, letters_email_html)
from .plantillas import TYPES, TYPE_LABEL_ES, METHOD_LABEL, REFERENCES, languages
from .parsers import extract, MAX_BYTES
from .models import ConfirmacionEnvio

MAX_SEND = 500


def _actor(user):
    return getattr(user, 'display_name', None) or getattr(user, 'full_name', None) or getattr(user, 'email', None)

router = APIRouter(prefix='/aud/confirmaciones-saldos', tags=['aud-confirmaciones-saldos'])

FORMATS = {
    'xlsx': (build_xlsx, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
    'docx': (build_docx, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
    'html': (build_html, 'text/html; charset=utf-8'),
    'pdf': (build_pdf, 'application/pdf'),
}


def access(project_id: int, user=Depends(require_staff), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project or not project.is_active or not user_can_access_project(db, user, project):
        raise HTTPException(403, 'Sin acceso al proyecto.')
    return project, user, db


async def bounded_body(request, limit):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > limit:
            raise HTTPException(413, 'Solicitud supera el tamaño permitido.')
        data.extend(chunk)
    return bytes(data)


async def request_data(request):
    try:
        data = json.loads(await bounded_body(request, 6 * 1024 * 1024))
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (ValueError, UnicodeError):
        raise HTTPException(400, 'Solicitud JSON no válida.') from None


def safe_calculate(data):
    try:
        return calculate(data)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise HTTPException(422, str(exc)) from None


@router.get('/{project_id}/context')
def context(project_id: int, authorized=Depends(access)):
    project, user, db = authorized
    client = db.get(Client, project.client_id)
    return {
        'client': client.name if client else '',
        'client_ruc': getattr(client, 'tax_id', '') if client else '',
        'year': project.period_end.year if project.period_end else '',
        'cutoff': project.period_end.isoformat() if project.period_end else '',
        'preparer': getattr(user, 'display_name', None) or getattr(user, 'full_name', None) or user.email,
        'types': [{'key': k, 'label': TYPE_LABEL_ES[k], 'default_method': v['default_method'],
                   'amount_applies': v['amount_applies']} for k, v in TYPES.items()],
        'methods': METHOD_LABEL,
        'languages': languages(),
        'references': REFERENCES,
    }


@router.post('/{project_id}/extract')
async def extraction(project_id: int, request: Request, filename: str = Query(..., max_length=200), authorized=Depends(access)):
    data = await bounded_body(request, MAX_BYTES)
    try:
        return await run_in_threadpool(extract, filename, data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.post('/{project_id}/process')
async def process(project_id: int, request: Request, authorized=Depends(access)):
    result = await run_in_threadpool(safe_calculate, await request_data(request))
    return {**result, 'schedules': schedules(result)}


@router.post('/{project_id}/download')
async def download(project_id: int, request: Request, format: str = Query(..., pattern='^(xlsx|docx|html|pdf)$'), authorized=Depends(access)):
    result = await run_in_threadpool(safe_calculate, await request_data(request))
    builder, mime = FORMATS[format]
    try:
        content = await run_in_threadpool(builder, result)
    except PDFNoDisponible as exc:
        raise HTTPException(503, str(exc)) from None
    return Response(content, media_type=mime, headers={
        'Content-Disposition': f'attachment; filename="AuditBrain_Confirmaciones.{format}"',
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _send_all(result, only_ids):
    """Envía cada carta al correo de su tercero (flujo estándar NIA 505).
    only_ids limita el envío a un subconjunto (reenvíos). Devuelve el detalle por carta."""
    reply_to = result['context'].get('auditor_email') or None
    to_by_id = {d['id']: d['to'] for d in result['dispatch']}
    results = []
    sent = 0
    for letter in result['letters']:
        cid = letter['id']
        if only_ids and cid not in only_ids:
            continue
        to = to_by_id.get(cid, '')
        if not to:
            results.append({'id': cid, 'to': '', 'status': 'sin_correo'})
            continue
        try:
            resp = send_email(to=to, subject=letter['subject'],
                              html=letter_email_html(result, letter), reply_to=reply_to)
            if resp:
                sent += 1
                results.append({'id': cid, 'to': to, 'status': 'enviado', 'provider_id': resp.get('id')})
            else:
                results.append({'id': cid, 'to': to, 'status': 'error'})
        except Exception as exc:  # noqa: BLE001
            results.append({'id': cid, 'to': to, 'status': 'error', 'detail': str(exc)[:200]})
    return {'sent': sent, 'total': len(results), 'results': results}


def _send_to_single(result, to):
    """Envía TODAS las cartas en un solo correo al destinatario indicado
    (p. ej. el buzón del auditor), para revisarlas o reenviarlas. Las respuestas
    de terceros siguen dirigidas al correo del auditor de la ficha."""
    ctx = result['context']
    reply_to = ctx.get('auditor_email') or None
    letters = result['letters']
    subject = f"Cartas de confirmación de saldos · {ctx.get('client') or ''} · corte {ctx.get('cutoff') or ''}"
    try:
        resp = send_email(to=to, subject=subject, html=letters_email_html(result), reply_to=reply_to)
        ok = bool(resp)
    except Exception as exc:  # noqa: BLE001
        return {'sent': 0, 'total': len(letters), 'destino': to,
                'results': [{'id': '(consolidado)', 'to': to, 'status': 'error', 'detail': str(exc)[:200]}]}
    return {
        'sent': len(letters) if ok else 0, 'total': len(letters), 'destino': to,
        'results': [{'id': '(consolidado)', 'to': to,
                     'status': 'enviado' if ok else 'error',
                     'provider_id': resp.get('id') if ok else None,
                     'cartas': len(letters)}],
    }


@router.post('/{project_id}/enviar')
async def enviar(project_id: int, request: Request, authorized=Depends(access)):
    project, user, db = authorized
    data = await request_data(request)
    only_ids = data.get('only_ids')
    if only_ids is not None and not isinstance(only_ids, list):
        raise HTTPException(400, 'only_ids debe ser una lista de identificadores.')
    send_to = (data.get('send_to') or '').strip() if isinstance(data.get('send_to'), str) else ''
    if send_to and not _EMAIL_RE.fullmatch(send_to):
        raise HTTPException(400, 'Correo de destino no válido.')
    result = await run_in_threadpool(safe_calculate, data)
    if result['totals']['count'] > MAX_SEND:
        raise HTTPException(422, f'Máximo {MAX_SEND} envíos por operación.')
    if send_to:
        summary = await run_in_threadpool(_send_to_single, result, send_to)
    else:
        summary = await run_in_threadpool(_send_all, result, set(only_ids) if only_ids else None)
    ctx = result['context']
    row = ConfirmacionEnvio(
        project_id=project.id, enviado_por=_actor(user), total=summary['total'],
        enviadas=summary['sent'], fallidas=summary['total'] - summary['sent'],
        cliente=ctx.get('client'), corte=ctx.get('cutoff'), idioma=ctx.get('language'),
        input_sha256=result.get('input_sha256'), resumen=summary['results'])
    db.add(row)
    db.commit()
    db.refresh(row)
    return {**summary, 'envio_id': row.id, 'enviado_en': row.enviado_en.isoformat()}


@router.get('/{project_id}/envios')
def envios(project_id: int, authorized=Depends(access)):
    project, user, db = authorized
    rows = (db.query(ConfirmacionEnvio)
            .filter(ConfirmacionEnvio.project_id == project.id)
            .order_by(ConfirmacionEnvio.enviado_en.desc()).limit(50).all())
    return [{'id': r.id, 'enviado_en': r.enviado_en.isoformat(), 'enviado_por': r.enviado_por,
             'total': r.total, 'enviadas': r.enviadas, 'fallidas': r.fallidas,
             'cliente': r.cliente, 'corte': r.corte, 'idioma': r.idioma,
             'input_sha256': r.input_sha256, 'resumen': r.resumen} for r in rows]
