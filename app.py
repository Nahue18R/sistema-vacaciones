import streamlit as st
from streamlit_gsheets import GSheetsConnection
import plotly.express as px  # <--- NUEVA LIBRERÍA PARA EL GRÁFICO
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
BASE_URL = "https://spring-hedgeless-eccentrically.ngrok-free.dev" 
WEBHOOK_SOLICITUD = f"{BASE_URL}/webhook/solicitud-vacaciones"
WEBHOOK_APROBACION = f"{BASE_URL}/webhook/solicitud-aprobada"

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
    df_empleados = conn.read(worksheet="Empleados", ttl="10m")
    df_solicitudes = conn.read(worksheet="Solicitudes", ttl=2)

    # Limpieza de columnas
    df_empleados.columns = df_empleados.columns.str.strip()
    df_solicitudes.columns = df_solicitudes.columns.str.strip()
    
    # Formateo de datos
    df_empleados['Fecha_Ingreso'] = pd.to_datetime(df_empleados['Fecha_Ingreso'], dayfirst=True, errors='coerce')
    df_empleados['Dias_Restantes'] = pd.to_numeric(df_empleados['Dias_Restantes'], errors='coerce').fillna(0)
    # ID como string limpio
    df_empleados['ID_Empleado'] = pd.to_numeric(df_empleados['ID_Empleado'], errors='coerce').fillna(0).astype(int).astype(str)

except Exception as e:
    time.sleep(2)
    st.rerun()

# --- 2. FUNCIONES MODIFICADAS ---

# MODIFICACIÓN: Ahora cuenta TODOS los días (Sábados y Domingos incluidos)
def calcular_dias_corridos(inicio, fin):
    delta = fin - inicio
    return delta.days + 1  # +1 para incluir el día de inicio también

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
                
                # MODIFICACION: Usamos la nueva funcion de dias corridos
                dias = calcular_dias_corridos(fi, ff)
                st.write(f"📅 Días totales a descontar: **{dias}**")
                
                if st.form_submit_button("Guardar", use_container_width=True):
                    if dias <= 0: st.error("Fechas incorrectas")
                    elif tipo == "Vacaciones" and dias > datos_emp['Dias_Restantes']: st.error("Sin saldo suficiente")
                    else:
                        # 1. Crear fila nueva
                        nuevo = pd.DataFrame([{ 
                            "ID_Solicitud": f"REQ-{len(df_solicitudes)+1000}",
                            "ID_Empleado": datos_emp['ID_Empleado'],
                            "Nombre_Empleado": empleado_selec,
                            "Tipo_Ausencia": tipo,
                            "Fecha_Inicio": fi.strftime("%Y-%m-%d"),
                            "Fecha_Fin": ff.strftime("%Y-%m-%d"),
                            "Total_Dias_Habiles": dias, # Guardamos dias corridos
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
            # MODIFICACION: Agregué la columna 'Total_Dias_Habiles' renombrada visualmente como 'Días'
            st.dataframe(
                h[['Fecha_Inicio', 'Fecha_Fin', 'Total_Dias_Habiles', 'Tipo_Ausencia', 'Estado']], 
                column_config={"Total_Dias_Habiles": "Días"}, # Renombramos cabecera
                hide_index=True, 
                use_container_width=True
            )
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
                    st.info("🔄 Procesando aprobación...")
                    
                    try:
                        # Leemos fresco para descontar
                        df_fresh = conn.read(worksheet="Empleados", ttl=0)
                        df_fresh.columns = df_fresh.columns.str.strip()
                        
                        id_buscado = str(r['ID_Empleado']).strip().replace(".0", "")
                        df_fresh['ID_Empleado'] = df_fresh['ID_Empleado'].astype(str).str.strip().str.replace(".0", "", regex=False)
                        
                        idx = df_fresh[df_fresh['ID_Empleado'] == id_buscado].index
                        
                        nuevo_saldo = 0
                        if not idx.empty:
                            saldo_anterior = df_fresh.at[idx[0], 'Dias_Restantes']
                            dias_a_descontar = r['Total_Dias_Habiles']
                            nuevo_saldo = saldo_anterior - dias_a_descontar
                            
                            # Guardamos nuevo saldo
                            df_fresh.at[idx[0], 'Dias_Restantes'] = nuevo_saldo
                            conn.update(worksheet="Empleados", data=df_fresh)
                            
                            # Actualizar estado Solicitud
                            df_solicitudes.at[i, 'Estado'] = 'Aprobado'
                            conn.update(worksheet="Solicitudes", data=df_solicitudes)

                            # Enviar Mail (n8n)
                            fecha_ret = pd.to_datetime(r['Fecha_Fin']) + timedelta(days=1)
                            payload = {
                                "legajo": str(r['ID_Empleado']),
                                "nombre": r['Nombre_Empleado'],
                                "tipo": r['Tipo_Ausencia'],
                                "desde": pd.to_datetime(r['Fecha_Inicio']).strftime("%d/%m/%Y"),
                                "hasta": pd.to_datetime(r['Fecha_Fin']).strftime("%d/%m/%Y"),
                                "dia_vuelve": fecha_ret.strftime("%d/%m/%Y"),
                                "dias_tomados": int(r['Total_Dias_Habiles']),
                                "dias_restantes": int(nuevo_saldo),
                                "email_jefe": "nruiz@open25.com.ar"
                            }
                            requests.post(WEBHOOK_APROBACION, json=payload, timeout=3)
                            
                            st.toast("✅ Aprobado y correo enviado")
                            time.sleep(2)
                            st.rerun()

                        else:
                            st.error(f"❌ Error: No encontré el legajo {id_buscado}.")

                    except Exception as e:
                        st.error(f"Error: {e}")
                    
                if c3.button("❌ Rechazar", key=f"n{i}", use_container_width=True):
                    df_solicitudes.at[i, 'Estado'] = 'Rechazado'
                    conn.update(worksheet="Solicitudes", data=df_solicitudes)
                    st.toast("❌ Rechazado")
                    time.sleep(1)
                    st.rerun()

# =======================================================
# PÁGINA 3: CALENDARIO (MODIFICADO TIPO GANTT)
# =======================================================
elif menu == "📅 Calendario":
    st.header("Cronograma de Vacaciones (Gantt)")
    
    if not df_solicitudes.empty:
        # Preparamos datos para Plotly
        df_cal = df_solicitudes.copy()
        
        # Filtramos solo Aprobados o Pendientes (Opcional, aquí muestro todo menos rechazados)
        df_cal = df_cal[df_cal['Estado'] != 'Rechazado']
        
        if not df_cal.empty:
            df_cal['Inicio'] = pd.to_datetime(df_cal['Fecha_Inicio'])
            df_cal['Fin'] = pd.to_datetime(df_cal['Fecha_Fin'])
            # Plotly necesita que el fin sea +1 día para que la barra se vea completa visualmente hasta el final del día
            df_cal['Fin_Visual'] = df_cal['Fin'] + timedelta(days=1)

            # CREAMOS EL DIAGRAMA DE GANTT
            fig = px.timeline(
                df_cal, 
                x_start="Inicio", 
                x_end="Fin_Visual", 
                y="Nombre_Empleado", 
                color="Tipo_Ausencia",
                hover_data=["Estado", "Total_Dias_Habiles"],
                title="Visualización de Ausencias"
            )
            
            # Ajustes visuales
            fig.update_yaxes(autorange="reversed", title="") # Para que los nombres salgan en orden
            fig.update_layout(
                xaxis_title="Fecha",
                showlegend=True,
                height=400 + (len(df_cal) * 20) # Altura dinámica
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay vacaciones activas para mostrar.")
    else:
        st.info("No hay registros.")



