"""El contrato de los tres cortes: qué es cada uno y en qué orden llegan.

No confundir con `cohortes.py`, que MIDE la permanencia de la cohorte entre dos
cortes. Aquí solo vive lo que define a los tres análisis de antigüedad como
conjunto: su rol por posición y la regla de que sus fechas van en orden
cronológico estricto.

POR QUÉ LA REGLA. Los archivos y sus fechas viajan por POSICIÓN: índice 0 es la
cohorte (t-2), índice 2 es el corte actual (t). El corte actual fija la
EXPOSICIÓN que se mide y la cohorte fija las TASAS, así que invertir el orden
no produce un error: produce otra medición, con la exposición del corte más
antiguo y unas tasas derivadas siguiendo la cartera hacia atrás en el tiempo.
Con los tres cortes de prueba, al revés daba 86.206,90 en vez de 208.943,84 sin
un solo hallazgo sobre el orden. Un dato de entrada que cambia el resultado en
silencio no es una variante: es un error de entrada, y se rechaza diciendo qué
hacer.

El orden es ESTRICTO: dos cortes con la misma fecha no abren ninguna ventana
entre sí, así que tampoco sirven para seguir una cohorte.
"""
from __future__ import annotations

from datetime import date

#: Rol de cada corte por su posición, en el mismo orden en que el router los
#: recibe. El nombre del archivo lo pone el cliente y puede decir cualquier
#: cosa; el rol lo fija la herramienta por la posición, y por eso el papel lo
#: imprime junto a la FECHA de ese mismo corte.
ROLES_DE_CORTE = ("cohorte (t-2)", "corte intermedio (t-1)", "corte actual (t)")


def validar_orden_cronologico(fechas: list[date]) -> None:
    """Exige que las tres fechas de corte vayan en orden cronológico estricto.

    Levanta `ValueError` -que el router traduce a un 400- nombrando el par
    concreto que está fuera de orden, con las dos fechas y con qué hacer. No
    reordena nada por su cuenta: los archivos y las fechas los empareja el
    auditor, y adivinar cuál de los dos está mal sería inventar la corrida.
    """
    if len(fechas) != len(ROLES_DE_CORTE):
        return
    for i in range(len(fechas) - 1):
        anterior, siguiente = fechas[i], fechas[i + 1]
        if siguiente > anterior:
            continue
        raise ValueError(
            f"Las fechas de corte deben ir en orden cronológico estricto: el archivo 1 es la "
            f"{ROLES_DE_CORTE[0]}, el archivo 2 el {ROLES_DE_CORTE[1]} y el archivo 3 el "
            f"{ROLES_DE_CORTE[2]}. La fecha del archivo {i + 2} ({siguiente.isoformat()}) no es "
            f"posterior a la del archivo {i + 1} ({anterior.isoformat()}). El corte actual fija "
            f"la exposición que se mide y la cohorte fija las tasas, así que con el orden "
            f"cambiado la corrida mediría otra cosa. Vuelva a subir los tres archivos del más "
            f"antiguo al más reciente, con su fecha de corte en el mismo orden, o corrija la "
            f"fecha equivocada."
        )
