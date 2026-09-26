"""Modelos de carta de circularización, multi-idioma. Sin IA ni red.

Los textos replican el formato real de la firma (AUDITCONSULTING / LANSEY):
la carta la firma un funcionario del cliente y se responde directamente al auditor
(NIA 505). El importe no se imprime en las cartas «en blanco» (el destinatario lo
declara), que es el método por defecto de la firma. Para agregar un idioma basta
con añadir una entrada a LANGS.
"""
import re as _re

METHODS = ('positiva', 'negativa', 'en_blanco')

FIRM_NAME = {
    'audit_consulting': 'AUDITCONSULTING AUDITORES CIA. LTDA.',
    'partner_auditing': 'PARTNER AUDITING CIA. LTDA.',
}

# Tipos de confirmación y su configuración transversal (no textual).
TYPES = {
    'bancos': {'default_method': 'en_blanco', 'amount_applies': True, 'intro_kind': 'confirm', 'ref_label': 'Cuenta(s)/Cliente Nº'},
    'cuentas_por_cobrar': {'default_method': 'en_blanco', 'amount_applies': True, 'intro_kind': 'default', 'ref_label': 'Documento/Factura Nº'},
    'proveedores': {'default_method': 'en_blanco', 'amount_applies': True, 'intro_kind': 'default', 'ref_label': 'Cuenta de proveedor Nº'},
    'relacionados': {'default_method': 'en_blanco', 'amount_applies': True, 'intro_kind': 'default', 'ref_label': 'Cuenta intercompañía Nº'},
    'seguros': {'default_method': 'en_blanco', 'amount_applies': False, 'intro_kind': 'confirm', 'ref_label': 'Póliza Nº'},
    'abogados': {'default_method': 'en_blanco', 'amount_applies': False, 'intro_kind': 'abogados', 'ref_label': 'Expediente/Caso Nº'},
    'inventarios_terceros': {'default_method': 'en_blanco', 'amount_applies': True, 'intro_kind': 'default', 'ref_label': 'Contrato/Bodega Nº'},
    'inversiones': {'default_method': 'en_blanco', 'amount_applies': True, 'intro_kind': 'confirm', 'ref_label': 'Cuenta de custodia Nº'},
}

REFERENCES = [
    {'title': 'NIA 505 · Confirmaciones externas: diseño, control por el auditor y evaluación de respuestas',
     'url': 'https://www.iaasb.org/publications/international-standard-auditing-505-external-confirmations'},
    {'title': 'NIA 500 · Evidencia de auditoría: fiabilidad de la evidencia de fuentes externas',
     'url': 'https://www.iaasb.org/publications/international-standard-auditing-500-audit-evidence'},
    {'title': 'NIA 501 · Litigios y reclamaciones (cartas a abogados)',
     'url': 'https://www.iaasb.org/publications/international-standard-auditing-501-audit-evidence-specific-considerations-selected-items'},
    {'title': 'NIA 240 y NIC 24 · Partes relacionadas: saldos, transacciones y riesgo de fraude',
     'url': 'https://www.ifrs.org/issued-standards/list-of-standards/ias-24-related-party-disclosures/'},
]

# Etiquetas de rubro y de idioma para las interfaces (auditor).
TYPE_LABEL_ES = {
    'bancos': 'Bancos e instituciones financieras', 'cuentas_por_cobrar': 'Clientes y cuentas por cobrar',
    'proveedores': 'Proveedores y cuentas por pagar', 'relacionados': 'Partes relacionadas',
    'seguros': 'Compañías de seguros y corredores', 'abogados': 'Abogados y asesores legales',
    'inventarios_terceros': 'Inventarios en poder de terceros', 'inversiones': 'Inversiones y custodios de valores',
}
METHOD_LABEL = {
    'positiva': 'Positiva (se solicita respuesta y se declara el saldo)',
    'negativa': 'Negativa (responder solo si hay desacuerdo)',
    'en_blanco': 'En blanco (el destinatario declara el saldo) — formato de la firma',
}

NOTES = [
    'Ficha del encargo declarada por el auditor; los importes se expresan en la moneda indicada.',
    'La muestra es la población seleccionada para circularizar; el auditor conserva el control del envío y la respuesta (NIA 505).',
    'Las cartas las firma un funcionario del cliente que autoriza la revelación; la respuesta se dirige directamente al auditor.',
    'El manifiesto de envío reúne destinatario, correo y asunto de cada carta; el envío efectivo lo realiza el auditor o el correo de la plataforma.',
    'Control de confirmaciones al estilo de la firma: enviado, recibido, saldo en libros, confirmado, diferencia, gestión y observación.',
    'La cobertura compara el importe circularizado con el saldo del mayor por rubro; una cobertura baja o una diferencia exigen procedimientos adicionales.',
    'Conclusión pendiente de juicio profesional y de la evaluación de las respuestas; este documento es un borrador para revisión.',
    'Preparado por y revisado por identifican responsables declarados; no equivalen a firma electrónica ni aprobación.',
]

SHEETS = ['00 Portada', '01 Muestra', '02 Cartas', '03 Envio', '04 Control', '05 Cobertura', '06 Conclusion', '07 Revision']
TITLES = ['Portada del encargo', 'Muestra a circularizar', 'Cartas generadas', 'Manifiesto de envío',
          'Control de confirmaciones', 'Cobertura por rubro', 'Conclusión del auditor', 'Control de revisión']

_MONTHS = {
    'es': ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'],
    'en': ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
    'fr': ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'],
    'pt': ['', 'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'],
}


def firm_name(firm):
    return FIRM_NAME.get(firm, firm)


def languages():
    return {code: L['label'] for code, L in LANGS.items()}


def fmt_date(iso, lang):
    """Fecha larga: 31 de agosto de 2026 / August 31, 2026. iso vacío → ''."""
    if not iso:
        return ''
    try:
        y, m, d = (int(x) for x in str(iso)[:10].split('-'))
        month = _MONTHS.get(lang, _MONTHS['es'])[m]
    except (ValueError, IndexError):
        return str(iso)
    if lang in ('es', 'pt'):
        return f'{d} de {month} de {y}'
    if lang == 'fr':
        return f'{d} {month} {y}'
    return f'{month} {d}, {y}'


# ------------------------------------------------------------------ idiomas ---
LANGS = {
    'es': {
        'label': 'Español',
        'salut': {'default': 'Señores:', 'abogados': 'Abogado(a):'},
        'presente': 'Presente.-',
        'greeting': {'default': 'De nuestras consideraciones:', 'seguros': 'Estimados señores:', 'abogados': 'De mis consideraciones:'},
        'channel': 'a la dirección electrónica {email}{tel}{addr}',
        'tel': ', teléfono {phone}',
        'addr': ', dirección: {address}',
        'intro': {
            'default': 'Para uso de nuestros auditores independientes {firm}, {channel}, en el examen de nuestros estados financieros al {cutoff}, solicitamos proporcionarles directamente la siguiente información:',
            'confirm': 'Para uso de nuestros auditores independientes {firm}, {channel}, solicitamos les confirmen directamente a los mencionados señores la siguiente información con corte al {cutoff}:',
            'abogados': 'Con motivo de la auditoría de nuestros estados financieros al {cutoff}, agradeceríamos a usted se digne informar directamente a nuestros auditores externos {firm}, {channel}, sobre los siguientes puntos que sean de su conocimiento:',
        },
        'items': {
            'bancos': [
                'Saldo de la(s) cuenta(s) corriente(s) y/o de ahorro(s), nacionales e internacionales, con su(s) número(s).',
                'Saldo(s) a favor o a cargo y descripción de la(s) cuenta(s).',
                'Restricciones impuestas o existentes sobre la(s) cuenta(s) y tasa de interés que devengan, si aplica.',
                'Personas autorizadas a firmar, incluyendo límites de autorización.',
                'Detalle de préstamos, líneas de crédito (aprobada y utilizada), documentos descontados, aceptaciones, fianzas y avales, cobranzas y otras operaciones, con tipo y número de operación, fechas de concesión y vencimiento, valor, tasa de interés, valor adeudado por capital e intereses (normales y de mora) y garantías.',
            ],
            'cuentas_por_cobrar': [
                'Saldo(s) por cobrar y/o por pagar con ustedes al {cutoff}.',
                'Monto de la facturación que les realizamos entre el {period_start} y el {cutoff}, incluyendo conceptos.',
                'Detalle de convenios, contratos y compromisos que mantienen con {client}.',
                'Cualquier otra información que considere de utilidad para nuestros auditores.',
            ],
            'proveedores': [
                'Saldo(s) por pagar o cobrar a ustedes al {cutoff}.',
                'Monto de compras o servicios contratados entre el {period_start} y el {cutoff}.',
                'Detalle de montos pagados por préstamos, dividendos u otros conceptos (especificar) en el período.',
                'Detalle de convenios, contratos, garantías y compromisos que mantienen con {client}.',
            ],
            'relacionados': [
                'Saldo(s) por pagar o cobrar a ustedes al {cutoff}.',
                'Monto de compras o servicios contratados entre el {period_start} y el {cutoff}.',
                'Detalle de montos pagados por préstamos, dividendos u otros conceptos (especificar) en el período.',
                'Detalle de convenios, contratos, garantías y compromisos que mantienen con {client}.',
            ],
            'seguros': [
                'Número de póliza.', 'Naturaleza de la cobertura.', 'Fecha de concesión y vencimiento.',
                'Monto de la prima.', 'Saldos pendientes de pago por concepto de primas y otros gastos.',
                'Endosos de pólizas efectuados a favor de terceros.',
                'Cualquier otra información relacionada con {client}.',
            ],
            'abogados': [
                'Existencia de trámites o procedimientos judiciales o extrajudiciales y juicios por o en contra de la compañía y su estado actual, indicando si podrían derivar en pasivos u obligaciones y su monto estimado.',
                'Cualquier otro asunto que, según su conocimiento, pudiera derivar en un posible pasivo y su monto estimado.',
                'Montos adeudados por la compañía a usted o a terceros, en asuntos en que hayan intervenido, al {cutoff}.',
            ],
            'inventarios_terceros': [
                'Cantidades y descripción de los bienes de {client} en su poder (depósito, consignación o maquila) al {cutoff}.',
                'Estado, ubicación y condiciones de custodia de los bienes.',
                'Valor de los bienes, si lo conocen, y restricciones o gravámenes que pesen sobre ellos.',
            ],
            'inversiones': [
                'Detalle de títulos e instrumentos financieros de {client} bajo su custodia o administración al {cutoff}.',
                'Cantidad, valor nominal y valor de mercado.',
                'Gravámenes, prendas o restricciones.',
                'Rendimientos devengados y no cobrados a la fecha de corte.',
            ],
        },
        'closing': {
            'default': 'Para cualquier aclaración o ampliación del texto de esta carta, solicitamos dirigirse directamente a nuestros auditores independientes {firm}.',
            'seguros': 'Sin otro particular por el momento, agradezco su amable atención y me suscribo con un atento saludo.',
            'abogados': 'La información citada se refiere en todos los casos al {cutoff}; agradeceremos que las cuestiones surgidas con posterioridad y hasta la fecha de su respuesta se hagan constar.',
        },
        'valediction': 'Atentamente,',
        'method': {
            'positiva': 'Según nuestros registros, el saldo a la fecha de corte es {amount}. Le agradeceremos confirmar directamente a nuestros auditores si coincide con sus registros; en caso de discrepancia, indique el detalle.',
            'negativa': 'Según nuestros registros, el saldo a la fecha de corte es {amount}. Le solicitamos comunicar a nuestros auditores únicamente si no coincide con sus registros; de no recibir respuesta, se entenderá conforme.',
            'en_blanco': '',
        },
        'deadline': 'Agradeceremos su respuesta a más tardar el {deadline}.',
        'ref_line': '{label}: {ref}.',
        'response_title': 'Confirmación a diligenciar por el destinatario (devolver a los auditores)',
        'response': {
            'positiva': ['Fecha de respuesta: ______________________',
                         '[  ] La información es CORRECTA.',
                         '[  ] La información es INCORRECTA. Saldo/valor según nuestros registros: __________________',
                         'Observaciones: ____________________________________________',
                         'Nombre y cargo de quien responde: _________________________',
                         'Firma y sello: ____________________________________________'],
            'en_blanco': ['Fecha de respuesta: ______________________',
                          'Saldo/valor a la fecha de corte: __________________________',
                          'Detalle o soportes adjuntos: ______________________________',
                          'Nombre y cargo de quien responde: _________________________',
                          'Firma y sello: ____________________________________________'],
        },
        'subject': {
            'bancos': 'Confirmación de saldos y operaciones bancarias al {cutoff}',
            'cuentas_por_cobrar': 'Confirmación de saldo por cobrar al {cutoff}',
            'proveedores': 'Confirmación de saldo por pagar al {cutoff}',
            'relacionados': 'Confirmación de saldos y transacciones entre relacionadas al {cutoff}',
            'seguros': 'Confirmación de pólizas, primas y siniestros al {cutoff}',
            'abogados': 'Confirmación de litigios, reclamos y contingencias al {cutoff}',
            'inventarios_terceros': 'Confirmación de bienes en depósito o consignación al {cutoff}',
            'inversiones': 'Confirmación de inversiones bajo custodia al {cutoff}',
        },
    },
    'en': {
        'label': 'English',
        'salut': {'default': 'Dear Sirs / Madams,', 'abogados': 'Dear Counsel,'},
        'presente': '',
        'greeting': {'default': '', 'seguros': '', 'abogados': ''},
        'channel': 'at the e-mail address {email}{tel}{addr}',
        'tel': ', telephone {phone}',
        'addr': ', address: {address}',
        'intro': {
            'default': 'For the use of our independent auditors {firm}, {channel}, in the examination of our financial statements as of {cutoff}, we kindly ask you to provide them directly with the following information:',
            'confirm': 'For the use of our independent auditors {firm}, {channel}, we kindly ask you to confirm the following information directly to them as of {cutoff}:',
            'abogados': 'In connection with the audit of our financial statements as of {cutoff}, we would appreciate it if you would report directly to our external auditors {firm}, {channel}, on the following matters within your knowledge:',
        },
        'items': {
            'bancos': [
                'Balance of checking and/or savings account(s), domestic and international, with their number(s).',
                'Balance(s) in favor or against, and description of the account(s).',
                'Restrictions imposed or existing on the account(s) and the interest rate they earn, if applicable.',
                'Persons authorized to sign, including authorization limits.',
                'Detail of loans, credit lines (approved and used), discounted notes, acceptances, guarantees and sureties, collections and other transactions, with type and number of operation, grant and maturity dates, amount, interest rate, amount owed for principal and interest (ordinary and default) and collateral.',
            ],
            'cuentas_por_cobrar': [
                'Account(s) receivable and/or payable with you as of {cutoff}.',
                'Amount we invoiced to you between {period_start} and {cutoff}, including the related concepts.',
                'Detail of agreements, contracts and commitments held with {client}.',
                'Any other information you consider useful for our auditors.',
            ],
            'proveedores': [
                'Account(s) payable or receivable with you as of {cutoff}.',
                'Amount of purchases or services contracted between {period_start} and {cutoff}.',
                'Detail of amounts paid for loans, dividends or any other concept (please specify) during the period.',
                'Detail of agreements, contracts, guarantees and commitments held with {client}.',
            ],
            'relacionados': [
                'Account(s) payable or receivable with you as of {cutoff}.',
                'Amount of purchases or services contracted between {period_start} and {cutoff}.',
                'Detail of amounts paid for loans, dividends or any other concept (please specify) during the period.',
                'Detail of agreements, contracts, guarantees and commitments held with {client}.',
            ],
            'seguros': [
                'Policy number.', 'Nature of the coverage.', 'Grant and maturity dates.', 'Premium amount.',
                'Amounts pending payment for premiums and other charges.',
                'Policy endorsements made in favor of third parties.',
                'Any other information related to {client}.',
            ],
            'abogados': [
                'Existence of judicial or extrajudicial proceedings and lawsuits by or against the company and their current status, indicating whether they could result in liabilities or obligations and their estimated amount.',
                'Any other matter that, to your knowledge, could result in a possible liability and its estimated amount.',
                'Amounts owed by the company to you or to third parties, in matters in which you have intervened, as of {cutoff}.',
            ],
            'inventarios_terceros': [
                'Quantities and description of goods owned by {client} held by you (deposit, consignment or tolling) as of {cutoff}.',
                'Condition, location and custody terms of the goods.',
                'Value of the goods, if known, and any restrictions or liens on them.',
            ],
            'inversiones': [
                'Detail of securities and financial instruments of {client} under your custody or administration as of {cutoff}.',
                'Quantity, nominal value and market value.', 'Liens, pledges or restrictions.',
                'Accrued and uncollected returns as of the cut-off date.',
            ],
        },
        'closing': {
            'default': 'For any clarification or expansion of this letter, please contact our independent auditors {firm} directly.',
            'seguros': 'With no further matters for the time being, we thank you for your kind attention.',
            'abogados': 'The information referred to relates in all cases to {cutoff}; we would appreciate that matters arising afterwards and up to the date of your reply also be stated.',
        },
        'valediction': 'Sincerely,',
        'method': {
            'positiva': 'According to our records, the balance as of the cut-off date is {amount}. We would appreciate your confirming directly to our auditors whether it agrees with your records; if not, please provide the detail.',
            'negativa': 'According to our records, the balance as of the cut-off date is {amount}. Please notify our auditors only if it does not agree with your records; if no reply is received, agreement will be assumed.',
            'en_blanco': '',
        },
        'deadline': 'We would appreciate your reply no later than {deadline}.',
        'ref_line': '{label}: {ref}.',
        'response_title': 'Confirmation to be completed by the recipient (return to the auditors)',
        'response': {
            'positiva': ['Reply date: ______________________',
                         '[  ] The information is CORRECT.',
                         '[  ] The information is INCORRECT. Balance/value per our records: __________________',
                         'Comments: ____________________________________________',
                         'Name and title of respondent: _________________________',
                         'Signature and stamp: ____________________________________________'],
            'en_blanco': ['Reply date: ______________________',
                          'Balance/value as of the cut-off date: __________________________',
                          'Detail or attached support: ______________________________',
                          'Name and title of respondent: _________________________',
                          'Signature and stamp: ____________________________________________'],
        },
        'subject': {
            'bancos': 'Confirmation of bank balances and transactions as of {cutoff}',
            'cuentas_por_cobrar': 'Confirmation of accounts receivable balance as of {cutoff}',
            'proveedores': 'Confirmation of accounts payable balance as of {cutoff}',
            'relacionados': 'Confirmation of related-party balances and transactions as of {cutoff}',
            'seguros': 'Confirmation of policies, premiums and claims as of {cutoff}',
            'abogados': 'Confirmation of litigation, claims and contingencies as of {cutoff}',
            'inventarios_terceros': 'Confirmation of goods on deposit or consignment as of {cutoff}',
            'inversiones': 'Confirmation of investments under custody as of {cutoff}',
        },
    },
    'fr': {
        'label': 'Français',
        'salut': {'default': 'Messieurs, Mesdames,', 'abogados': 'Maître,'},
        'presente': '',
        'greeting': {'default': '', 'seguros': '', 'abogados': ''},
        'channel': 'à l’adresse électronique {email}{tel}{addr}',
        'tel': ', téléphone {phone}',
        'addr': ', adresse : {address}',
        'intro': {
            'default': 'À l’usage de nos auditeurs indépendants {firm}, {channel}, dans le cadre de l’examen de nos états financiers au {cutoff}, nous vous prions de leur communiquer directement les informations suivantes :',
            'confirm': 'À l’usage de nos auditeurs indépendants {firm}, {channel}, nous vous prions de bien vouloir leur confirmer directement les informations suivantes au {cutoff} :',
            'abogados': 'Dans le cadre de l’audit de nos états financiers au {cutoff}, nous vous saurions gré d’informer directement nos auditeurs externes {firm}, {channel}, sur les points suivants dont vous auriez connaissance :',
        },
        'items': {
            'bancos': [
                'Solde du/des compte(s) courant(s) et/ou d’épargne, nationaux et internationaux, avec leur(s) numéro(s).',
                'Solde(s) en faveur ou à charge et description du/des compte(s).',
                'Restrictions imposées ou existantes sur le(s) compte(s) et taux d’intérêt qu’ils portent, le cas échéant.',
                'Personnes autorisées à signer, y compris les limites d’autorisation.',
                'Détail des prêts, lignes de crédit (accordée et utilisée), effets escomptés, acceptations, cautions et garanties, encaissements et autres opérations, avec le type et le numéro d’opération, les dates d’octroi et d’échéance, le montant, le taux d’intérêt, le montant dû en capital et intérêts (ordinaires et de retard) et les sûretés.',
            ],
            'cuentas_por_cobrar': [
                'Solde(s) à recevoir et/ou à payer avec vous au {cutoff}.',
                'Montant de la facturation que nous vous avons adressée entre le {period_start} et le {cutoff}, en précisant les concepts.',
                'Détail des conventions, contrats et engagements que vous détenez avec {client}.',
                'Toute autre information que vous jugez utile pour nos auditeurs.',
            ],
            'proveedores': [
                'Solde(s) à payer ou à recevoir avec vous au {cutoff}.',
                'Montant des achats ou services contractés entre le {period_start} et le {cutoff}.',
                'Détail des montants payés au titre de prêts, dividendes ou tout autre concept (à préciser) durant la période.',
                'Détail des conventions, contrats, garanties et engagements que vous détenez avec {client}.',
            ],
            'relacionados': [
                'Solde(s) à payer ou à recevoir avec vous au {cutoff}.',
                'Montant des achats ou services contractés entre le {period_start} et le {cutoff}.',
                'Détail des montants payés au titre de prêts, dividendes ou tout autre concept (à préciser) durant la période.',
                'Détail des conventions, contrats, garanties et engagements que vous détenez avec {client}.',
            ],
            'seguros': [
                'Numéro de police.', 'Nature de la couverture.', 'Dates d’octroi et d’échéance.',
                'Montant de la prime.', 'Soldes en attente de paiement au titre des primes et autres frais.',
                'Avenants de polices établis en faveur de tiers.',
                'Toute autre information relative à {client}.',
            ],
            'abogados': [
                'Existence de procédures judiciaires ou extrajudiciaires et de litiges intentés par ou contre la société et leur état actuel, en indiquant s’ils pourraient donner lieu à des passifs ou obligations et leur montant estimé.',
                'Toute autre affaire qui, à votre connaissance, pourrait donner lieu à un passif éventuel et son montant estimé.',
                'Montants dus par la société à vous-même ou à des tiers, dans les affaires où vous êtes intervenu, au {cutoff}.',
            ],
            'inventarios_terceros': [
                'Quantités et description des biens appartenant à {client} détenus par vous (dépôt, consignation ou façonnage) au {cutoff}.',
                'État, emplacement et conditions de garde des biens.',
                'Valeur des biens, si elle est connue, et toute restriction ou charge les grevant.',
            ],
            'inversiones': [
                'Détail des titres et instruments financiers de {client} sous votre garde ou administration au {cutoff}.',
                'Quantité, valeur nominale et valeur de marché.', 'Charges, nantissements ou restrictions.',
                'Rendements courus et non encaissés à la date d’arrêté.',
            ],
        },
        'closing': {
            'default': 'Pour toute précision ou complément concernant la présente lettre, veuillez vous adresser directement à nos auditeurs indépendants {firm}.',
            'seguros': 'Sans autre point pour le moment, nous vous remercions de votre aimable attention.',
            'abogados': 'Les informations demandées se rapportent dans tous les cas au {cutoff} ; nous vous saurions gré d’y ajouter les éléments survenus postérieurement, jusqu’à la date de votre réponse.',
        },
        'valediction': 'Veuillez agréer nos salutations distinguées,',
        'method': {
            'positiva': 'Selon nos registres, le solde à la date d’arrêté est de {amount}. Nous vous saurions gré de confirmer directement à nos auditeurs s’il concorde avec vos registres ; à défaut, veuillez en préciser le détail.',
            'negativa': 'Selon nos registres, le solde à la date d’arrêté est de {amount}. Veuillez informer nos auditeurs uniquement s’il ne concorde pas avec vos registres ; à défaut de réponse, l’accord sera présumé.',
            'en_blanco': '',
        },
        'deadline': 'Nous vous saurions gré de répondre au plus tard le {deadline}.',
        'ref_line': '{label} : {ref}.',
        'response_title': 'Confirmation à compléter par le destinataire (à retourner aux auditeurs)',
        'response': {
            'positiva': ['Date de réponse : ______________________',
                         '[  ] Les informations sont EXACTES.',
                         '[  ] Les informations sont INEXACTES. Solde/valeur selon nos registres : __________________',
                         'Observations : ____________________________________________',
                         'Nom et fonction du signataire : _________________________',
                         'Signature et cachet : ____________________________________________'],
            'en_blanco': ['Date de réponse : ______________________',
                          'Solde/valeur à la date d’arrêté : __________________________',
                          'Détail ou pièces jointes : ______________________________',
                          'Nom et fonction du signataire : _________________________',
                          'Signature et cachet : ____________________________________________'],
        },
        'subject': {
            'bancos': 'Confirmation des soldes et opérations bancaires au {cutoff}',
            'cuentas_por_cobrar': 'Confirmation du solde clients au {cutoff}',
            'proveedores': 'Confirmation du solde fournisseurs au {cutoff}',
            'relacionados': 'Confirmation des soldes et opérations entre parties liées au {cutoff}',
            'seguros': 'Confirmation des polices, primes et sinistres au {cutoff}',
            'abogados': 'Confirmation des litiges, réclamations et passifs éventuels au {cutoff}',
            'inventarios_terceros': 'Confirmation des biens en dépôt ou consignation au {cutoff}',
            'inversiones': 'Confirmation des placements sous garde au {cutoff}',
        },
    },
    'pt': {
        'label': 'Português',
        'salut': {'default': 'Prezados Senhores,', 'abogados': 'Prezado(a) Advogado(a),'},
        'presente': '',
        'greeting': {'default': '', 'seguros': '', 'abogados': ''},
        'channel': 'para o endereço eletrônico {email}{tel}{addr}',
        'tel': ', telefone {phone}',
        'addr': ', endereço: {address}',
        'intro': {
            'default': 'Para uso dos nossos auditores independentes {firm}, {channel}, no exame das nossas demonstrações financeiras em {cutoff}, solicitamos que lhes forneçam diretamente as seguintes informações:',
            'confirm': 'Para uso dos nossos auditores independentes {firm}, {channel}, solicitamos que confirmem diretamente a eles as seguintes informações com data de corte em {cutoff}:',
            'abogados': 'Em razão da auditoria das nossas demonstrações financeiras em {cutoff}, agradecemos que informem diretamente aos nossos auditores externos {firm}, {channel}, sobre os seguintes pontos de seu conhecimento:',
        },
        'items': {
            'bancos': [
                'Saldo da(s) conta(s) corrente(s) e/ou poupança, nacionais e internacionais, com seu(s) número(s).',
                'Saldo(s) a favor ou a cargo e descrição da(s) conta(s).',
                'Restrições impostas ou existentes sobre a(s) conta(s) e a taxa de juros que rendem, se aplicável.',
                'Pessoas autorizadas a assinar, incluindo limites de autorização.',
                'Detalhe de empréstimos, linhas de crédito (aprovada e utilizada), títulos descontados, aceites, fianças e avais, cobranças e demais operações, com tipo e número da operação, datas de concessão e vencimento, valor, taxa de juros, valor devido de principal e juros (normais e de mora) e garantias.',
            ],
            'cuentas_por_cobrar': [
                'Saldo(s) a receber e/ou a pagar com vocês em {cutoff}.',
                'Montante do faturamento que emitimos a vocês entre {period_start} e {cutoff}, incluindo os conceitos.',
                'Detalhe de convênios, contratos e compromissos mantidos com {client}.',
                'Qualquer outra informação que considerem útil para os nossos auditores.',
            ],
            'proveedores': [
                'Saldo(s) a pagar ou a receber com vocês em {cutoff}.',
                'Montante de compras ou serviços contratados entre {period_start} e {cutoff}.',
                'Detalhe de valores pagos por empréstimos, dividendos ou qualquer outro conceito (especificar) no período.',
                'Detalhe de convênios, contratos, garantias e compromissos mantidos com {client}.',
            ],
            'relacionados': [
                'Saldo(s) a pagar ou a receber com vocês em {cutoff}.',
                'Montante de compras ou serviços contratados entre {period_start} e {cutoff}.',
                'Detalhe de valores pagos por empréstimos, dividendos ou qualquer outro conceito (especificar) no período.',
                'Detalhe de convênios, contratos, garantias e compromissos mantidos com {client}.',
            ],
            'seguros': [
                'Número da apólice.', 'Natureza da cobertura.', 'Datas de concessão e vencimento.',
                'Valor do prêmio.', 'Saldos pendentes de pagamento a título de prêmios e outras despesas.',
                'Endossos de apólices efetuados a favor de terceiros.',
                'Qualquer outra informação relacionada com {client}.',
            ],
            'abogados': [
                'Existência de processos judiciais ou extrajudiciais e ações movidas pela ou contra a companhia e seu estado atual, indicando se poderiam resultar em passivos ou obrigações e seu valor estimado.',
                'Qualquer outro assunto que, segundo seu conhecimento, possa resultar em um possível passivo e seu valor estimado.',
                'Valores devidos pela companhia a você ou a terceiros, em assuntos em que tenha atuado, em {cutoff}.',
            ],
            'inventarios_terceros': [
                'Quantidades e descrição dos bens de {client} em seu poder (depósito, consignação ou industrialização) em {cutoff}.',
                'Estado, localização e condições de guarda dos bens.',
                'Valor dos bens, se conhecido, e restrições ou ônus que recaiam sobre eles.',
            ],
            'inversiones': [
                'Detalhe de títulos e instrumentos financeiros de {client} sob sua custódia ou administração em {cutoff}.',
                'Quantidade, valor nominal e valor de mercado.', 'Ônus, penhores ou restrições.',
                'Rendimentos incorridos e não recebidos na data de corte.',
            ],
        },
        'closing': {
            'default': 'Para qualquer esclarecimento ou complemento do texto desta carta, solicitamos dirigir-se diretamente aos nossos auditores independentes {firm}.',
            'seguros': 'Sem outro particular no momento, agradecemos sua gentil atenção.',
            'abogados': 'As informações citadas referem-se em todos os casos a {cutoff}; agradecemos que as questões surgidas posteriormente e até a data da sua resposta também sejam informadas.',
        },
        'valediction': 'Atenciosamente,',
        'method': {
            'positiva': 'Segundo os nossos registros, o saldo na data de corte é de {amount}. Agradecemos confirmar diretamente aos nossos auditores se coincide com os seus registros; em caso de divergência, indique o detalhe.',
            'negativa': 'Segundo os nossos registros, o saldo na data de corte é de {amount}. Solicitamos comunicar aos nossos auditores apenas se não coincidir com os seus registros; não havendo resposta, será presumida a conformidade.',
            'en_blanco': '',
        },
        'deadline': 'Agradecemos sua resposta até {deadline}.',
        'ref_line': '{label}: {ref}.',
        'response_title': 'Confirmação a ser preenchida pelo destinatário (devolver aos auditores)',
        'response': {
            'positiva': ['Data da resposta: ______________________',
                         '[  ] As informações estão CORRETAS.',
                         '[  ] As informações estão INCORRETAS. Saldo/valor segundo nossos registros: __________________',
                         'Observações: ____________________________________________',
                         'Nome e cargo de quem responde: _________________________',
                         'Assinatura e carimbo: ____________________________________________'],
            'en_blanco': ['Data da resposta: ______________________',
                          'Saldo/valor na data de corte: __________________________',
                          'Detalhe ou documentos anexos: ______________________________',
                          'Nome e cargo de quem responde: _________________________',
                          'Assinatura e carimbo: ____________________________________________'],
        },
        'subject': {
            'bancos': 'Confirmação de saldos e operações bancárias em {cutoff}',
            'cuentas_por_cobrar': 'Confirmação de saldo a receber em {cutoff}',
            'proveedores': 'Confirmação de saldo a pagar em {cutoff}',
            'relacionados': 'Confirmação de saldos e transações entre partes relacionadas em {cutoff}',
            'seguros': 'Confirmação de apólices, prêmios e sinistros em {cutoff}',
            'abogados': 'Confirmação de litígios, reclamações e contingências em {cutoff}',
            'inventarios_terceros': 'Confirmação de bens em depósito ou consignação em {cutoff}',
            'inversiones': 'Confirmação de investimentos sob custódia em {cutoff}',
        },
    },
}


def _channel(L, ctx):
    tel = L['tel'].format(phone=ctx['auditor_phone']) if ctx.get('auditor_phone') else ''
    addr = L['addr'].format(address=ctx['auditor_address']) if ctx.get('auditor_address') else ''
    return L['channel'].format(email=ctx['auditor_email'], tel=tel, addr=addr)


def render_letter(ctx, item, amount_text):
    """Carta estructurada en el idioma del encargo. amount_text ya formateado o None."""
    lang = ctx.get('language', 'es')
    L = LANGS.get(lang, LANGS['es'])
    key = item['type']
    spec = TYPES[key]
    method = item['method']
    firm = firm_name(ctx['firm'])
    cutoff_long = fmt_date(ctx['cutoff'], lang)
    period_start = fmt_date(ctx.get('period_start') or f"{str(ctx['cutoff'])[:4]}-01-01", lang)
    fmt = dict(firm=firm, channel=_channel(L, ctx), cutoff=cutoff_long,
               period_start=period_start, client=ctx['client'])

    # Encabezado
    place = ctx.get('place', '')
    letter_date = fmt_date(ctx.get('letter_date') or ctx['cutoff'], lang)
    header = f'{place}, {letter_date}' if place else letter_date
    salut = L['salut'].get(key, L['salut']['default'])
    salutation = [header, '', salut, item['entity']]
    if item.get('contact_address'):
        salutation.append(item['contact_address'])
    if L['presente']:
        salutation.append(L['presente'])
    greeting = L['greeting'].get(key, L['greeting']['default'])
    if greeting:
        salutation += ['', greeting]
    if item.get('contact_name'):
        salutation.append(f'({item["contact_name"]})')

    # Cuerpo
    tidy = lambda s: _re.sub(r'(?<!\.)\.\.(?!\.)', '.', s)
    intro = tidy(L['intro'][spec['intro_kind']].format(**fmt))
    items = [tidy(b.format(**fmt)) for b in L['items'][key]]
    blocks = [intro]
    if method in ('positiva', 'negativa') and amount_text:
        blocks.append(L['method'][method].format(amount=amount_text))
    if item.get('account_ref'):
        blocks.append(L['ref_line'].format(label=spec['ref_label'], ref=item['account_ref']))
    if item.get('notes'):
        blocks.append(item['notes'])
    closing = tidy(L['closing'].get(key, L['closing']['default']).format(**fmt))
    blocks.append(closing)
    if ctx.get('response_deadline'):
        blocks.append(L['deadline'].format(deadline=fmt_date(ctx['response_deadline'], lang)))

    signature = [L['valediction'], '', ctx['signatory'], ctx.get('signatory_role', ''), ctx['client']]

    response = None
    if ctx.get('include_response_slip') and method != 'negativa':
        response = L['response']['positiva' if method == 'positiva' else 'en_blanco']

    return {
        'type': key, 'type_label': TYPE_LABEL_ES[key], 'method': method,
        'method_label': METHOD_LABEL[method], 'language': lang,
        'subject': L['subject'][key].format(cutoff=cutoff_long),
        'salutation': salutation, 'items': items, 'blocks': blocks,
        'signature': [s for s in signature if s],
        'response_title': L['response_title'] if response else None,
        'response_lines': response,
    }
