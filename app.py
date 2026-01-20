import streamlit as st
from streamlit_gsheets import GSheetsConnection
from streamlit_calendar import calendar
import pandas as pd
from datetime import timedelta, date, datetime
import requests
import time
import os
from dateutil.relativedelta import relativedelta

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema RRHH - Open25", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# ⚠️ TUS LINKS DE NGROK
# ==========================================
# Pega aquí tu link actual de hoy
BASE_URL = "https://spring-hedgeless-eccentrically.ngrok-free.dev" 

WEBHOOK_SOLICITUD = f"{BASE_URL}/webhook-test/solicitud-vacaciones"
WEBHOOK_APROBACION = f"{BASE_URL}/webhook-test/solicitud-aprobada"

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .stMetric {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .nombre-titulo {
        font-size: 28px !important;
        font-weight: 800 !important;
        color: #1e293b;
        margin-bottom: 0px;
    }
    .puesto-subtitulo {
        font-size: 16px;
        color: #64748b;
        font-weight: 500;
        margin-bottom: 15px;
    }
    .stButton button {
        border-radius: 8px;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# --- LOGIN ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

def login():
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("## 🔒 Acceso Supervisores")
        with st.form("login"):
            usr = st.text_input("Usuario")
            pwd = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Ingresar", use_container_width=True):
                if usr == "OFICINA" and pwd == "123456":
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")

if not st.session_state.logged_in:
    login()
    st.stop()

# --- 1. CONEXIÓN Y DATOS ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_feriados = conn.read(worksheet="Feriados", ttl="1d") 
    df_empleados = conn.read(worksheet="Empleados", ttl="10m")
    df_solicitudes = conn.read(worksheet="Solicitudes", ttl=2)

    # Limpieza de columnas
    df_empleados.columns = df_empleados.columns.str.strip()
    df_solicitudes.columns = df_solicitudes.columns.str.strip()
    
    # Formateo de datos
    df_feriados['Fecha'] = pd.to_datetime(df_feriados['Fecha'], dayfirst=True, errors='coerce').dt.date
    df_empleados['Fecha_Ingreso'] = pd.to_datetime(df_empleados['Fecha_Ingreso'], dayfirst=True, errors='coerce')
    df_empleados['Dias_Restantes'] = pd.to_numeric(df_empleados['Dias_Restantes'], errors='coerce').fillna(0)
    # ID como string limpio
    df_empleados['ID_Empleado'] = pd.to_numeric(df_empleados['ID_Empleado'], errors='coerce').fillna(0).astype(int).astype(str)

except Exception as e:
    time.sleep(2)
    st.rerun()

# --- 2. FUNCIONES ---
def calcular_dias_habiles(inicio, fin, feriados_lista):
    dias_totales = 0
    fecha_actual = inicio
    while fecha_actual <= fin:
        es_finde = fecha_actual.weekday() >= 5
        es_feriado = fecha_actual in feriados_lista
        if not es_finde and not es_feriado:
            dias_totales += 1
        fecha_actual += timedelta(days=1)
    return dias_totales

def calcular_antiguedad_texto(fecha_inicio):
    if pd.isna(fecha_inicio): return "⚠️ Revisar fecha en Excel"
    hoy = datetime.now()
    diferencia = relativedelta(hoy, fecha_inicio)
    texto = []
    if diferencia.years > 0: texto.append(f"{diferencia.years} años")
    if diferencia.months > 0: texto.append(f"{diferencia.months} meses")
    if not texto: return "Reciente ingreso"
    return " hace " + " y ".join(texto)

def obtener_foto(legajo):
    extensiones = ['.jpg', '.jpeg', '.png', '.JPG', '.PNG']
    for ext in extensiones:
        archivo = f"{legajo}{ext}"
        if os.path.exists(archivo): return archivo
    return "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"

# --- 3. MENÚ LATERAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320295.png", width=60)
    st.title("Panel RRHH")
    menu = st.radio("Navegación", ["👥 Gestión de Personal", "✅ Aprobaciones", "📅 Calendario"])
    st.markdown("---")
    if st.button("Salir"):
        st.session_state.logged_in = False
        st.rerun()

# =======================================================
# PÁGINA 1: GESTIÓN
# =======================================================
if menu == "👥 Gestión de Personal":
    st.header("Gestión de Colaboradores")
    
    lista_nombres = df_empleados['Nombre_Completo'].unique()
    col_sel, _ = st.columns([1, 2])
    with col_sel:
        empleado_selec = st.selectbox("Buscar Colaborador:", lista_nombres)

    datos_emp = df_empleados[df_empleados['Nombre_Completo'] == empleado_selec].iloc[0]

    st.markdown("---")
    col_foto, col_info, col_kpi = st.columns([1, 3, 2])
    
    with col_foto:
        legajo_actual = str(datos_emp['ID_Empleado'])
        st.image(obtener_foto(legajo_actual), width=130)
        link_docs = datos_emp.get('Link_Legajo', '#')
        if pd.notna(link_docs) and str(link_docs).strip() not in ["", "#"]:
             st.link_button("📂 Ver Legajo", link_docs, use_container_width=True)

    with col_info:
        st.markdown(f'<div class="nombre-titulo">{datos_emp["Nombre_Completo"]}</div>', unsafe_allow_html=True)
        fecha_ing = datos_emp.get('Fecha_Ingreso', pd.NaT)
        
        if pd.isna(fecha_ing):
             fecha_texto = "Sin dato"
             texto_antiguedad = "-"
        else:
             fecha_texto = fecha_ing.strftime('%d/%m/%Y')
             texto_antiguedad = calcular_antiguedad_texto(fecha_ing)
        
        st.markdown(f'<div class="puesto-subtitulo">Legajo: {datos_emp["ID_Empleado"]} | Ingreso: {fecha_texto}</div>', unsafe_allow_html=True)
        
        if texto_antiguedad != "-": st.success(f"🏅 **Antigüedad:** {texto_antiguedad}")
        else: st.warning("⚠️ No se pudo calcular antigüedad")
        
        st.info(f"ℹ️ **Desglose:** {datos_emp.get('Detalle_Vacaciones', 'Sin detalle')}")

    with col_kpi:
        st.metric("Saldo Disponible", f"{int(datos_emp['Dias_Restantes'])} días")
        pendientes = len(df_solicitudes[(df_solicitudes['Nombre_Empleado'] == empleado_selec) & (df_solicitudes['Estado'] == 'Pendiente')])
        st.metric("Solicitudes Activas", pendientes)

    st.markdown("---")

    c_form, c_hist = st.columns([1, 1.3])
    with c_form:
        with st.container(border=True):
            st.subheader("📝 Nueva Solicitud")
            with st.form("form_vacs"):
                tipo = st.selectbox("Tipo", ["Vacaciones", "Enfermedad", "Trámite", "Home Office", "Licencia"])
                c1, c2 = st.columns(2)
                fi = c1.date_input("Desde", date.today())
                ff = c2.date_input("Hasta", date.today())
                
                l_sust = df_empleados[df_empleados['Nombre_Completo'] != empleado_selec]['Nombre_Completo'].tolist()
                l_sust.insert(0, "No precisa")
                sust = st.selectbox("Sustituto", l_sust)
                motivo = st.text_area("Observaciones")
                
                feriados = df_feriados['Fecha'].tolist() if not df_feriados.empty else []
                dias = calcular_dias_habiles(fi, ff, feriados)
                st.write(f"📅 Días hábiles: **{dias}**")
                
                if st.form_submit_button("Guardar", use_container_width=True):
                    if dias <= 0: st.error("Fechas incorrectas")
                    elif tipo == "Vacaciones" and dias > datos_emp['Dias_Restantes']: st.error("Sin saldo")
                    else:
                        # 1. Crear fila nueva
                        nuevo = pd.DataFrame([{ 
                            "ID_Solicitud": f"REQ-{len(df_solicitudes)+1000}",
                            "ID_Empleado": datos_emp['ID_Empleado'],
                            "Nombre_Empleado": empleado_selec,
                            "Tipo_Ausencia": tipo,
                            "Fecha_Inicio": fi.strftime("%Y-%m-%d"),
                            "Fecha_Fin": ff.strftime("%Y-%m-%d"),
                            "Total_Dias_Habiles": dias,
                            "Sustituto_Asignado": sust,
                            "Estado": "Pendiente",
                            "Motivo_Comentario": motivo
                        }])
                        # 2. Guardar en Excel
                        conn.update(worksheet="Solicitudes", data=pd.concat([df_solicitudes, nuevo], ignore_index=True))
                        
                        # 3. Avisar al jefe (Webhook)
                        try:
                            ret = ff + timedelta(days=1)
                            req_data = {
                                "legajo": str(datos_emp['ID_Empleado']),
                                "nombre": empleado_selec,
                                "tipo": tipo,
                                "desde": fi.strftime("%d/%m/%Y"),
                                "hasta": ff.strftime("%d/%m/%Y"),
                                "dia_vuelve": ret.strftime("%d/%m/%Y"),
                                "dias_tomados": int(dias),
                                "dias_restantes": int(datos_emp['Dias_Restantes'] - dias),
                                "email_jefe": "nruiz@open25.com.ar"
                            }
                            requests.post(WEBHOOK_SOLICITUD, json=req_data, timeout=2)
                        except: pass
                        
                        st.success("¡Registrado!")
                        time.sleep(1)
                        st.rerun()

    with c_hist:
        st.subheader("Historial")
        h = df_solicitudes[df_solicitudes['Nombre_Empleado'] == empleado_selec].sort_index(ascending=False)
        if not h.empty:
            st.dataframe(h[['Fecha_Inicio', 'Fecha_Fin', 'Tipo_Ausencia', 'Estado']], hide_index=True, use_container_width=True)
        else: st.info("Sin registros.")

# =======================================================
# PÁGINA 2: APROBACIONES
# =======================================================
elif menu == "✅ Aprobaciones":
    st.header("Centro de Aprobaciones")
    pend = df_solicitudes[df_solicitudes['Estado'] == 'Pendiente']
    
    if pend.empty: 
        st.success("Todo al día 🚀")
    else:
        st.write(f"Tienes {len(pend)} solicitudes pendientes.")
        for i, r in pend.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([2,2,1])
                c1.markdown(f"**{r['Nombre_Empleado']}**")
                c1.caption(f"Tipo: {r['Tipo_Ausencia']}")
                c1.text(f"Legajo: {r['ID_Empleado']}")
                
                c2.write(f"📅 **{r['Fecha_Inicio']}** al **{r['Fecha_Fin']}**")
                c2.info(f"⏳ Días a descontar: {r['Total_Dias_Habiles']}")
                
                if c3.button("✅ Aprobar", key=f"y{i}", use_container_width=True):
                    # 1. Cambiar estado
                    df_solicitudes.at[i, 'Estado'] = 'Aprobado'
                    conn.update(worksheet="Solicitudes", data=df_solicitudes)
                    
                    # 2. Descontar saldo (Leemos fresco)
                    df_fresh = conn.read(worksheet="Empleados", ttl=0)
                    df_fresh.columns = df_fresh.columns.str.strip()
                    df_fresh['ID_Empleado'] = pd.to_numeric(df_fresh['ID_Empleado'], errors='coerce').fillna(0).astype(int).astype(str)
                    
                    idx = df_fresh[df_fresh['ID_Empleado'] == str(r['ID_Empleado'])].index
                    nuevo_saldo = 0
                    if not idx.empty:
                        nuevo_saldo = df_fresh.at[idx[0], 'Dias_Restantes'] - r['Total_Dias_Habiles']
                        df_fresh.at[idx[0], 'Dias_Restantes'] = nuevo_saldo
                        conn.update(worksheet="Empleados", data=df_fresh)

                    # 3. Mandar mail
                    try: 
                        fecha_ret = pd.to_datetime(r['Fecha_Fin']) + timedelta(days=1)
                        requests.post(WEBHOOK_APROBACION, json={
                            "legajo": str(r['ID_Empleado']),
                            "nombre": r['Nombre_Empleado'],
                            "tipo": r['Tipo_Ausencia'],
                            "desde": pd.to_datetime(r['Fecha_Inicio']).strftime("%d/%m/%Y"),
                            "hasta": pd.to_datetime(r['Fecha_Fin']).strftime("%d/%m/%Y"),
                            "dia_vuelve": fecha_ret.strftime("%d/%m/%Y"),
                            "dias_tomados": int(r['Total_Dias_Habiles']),
                            "dias_restantes": int(nuevo_saldo),
                            "email_jefe": "nruiz@open25.com.ar"
                        }, timeout=3)
                    except: pass
                    
                    st.toast("✅ Aprobado")
                    time.sleep(1)
                    st.rerun()
                    
                if c3.button("❌ Rechazar", key=f"n{i}", use_container_width=True):
                    df_solicitudes.at[i, 'Estado'] = 'Rechazado'
                    conn.update(worksheet="Solicitudes", data=df_solicitudes)
                    st.toast("❌ Rechazado")
                    time.sleep(1)
                    st.rerun()

# =======================================================
# PÁGINA 3: CALENDARIO
# =======================================================
elif menu == "📅 Calendario":
    st.header("Calendario Global")
    ev = []
    if not df_solicitudes.empty:
        for _, r in df_solicitudes.iterrows():
            if pd.notna(r['Fecha_Inicio']):
                c = "#f59e0b" if r['Estado'] == 'Pendiente' else "#10b981"
                if r['Estado'] == 'Rechazado': c = "#ef4444"
                ev.append({
                    "title": r['Nombre_Empleado'], 
                    "start": str(r['Fecha_Inicio']), 
                    "end": str(pd.to_datetime(r['Fecha_Fin']) + timedelta(days=1)), 
                    "color": c
                })
    calendar(events=ev, options={"initialView": "dayGridMonth", "locale": "es"})


