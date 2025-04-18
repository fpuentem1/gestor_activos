# ======================================================
# IMPORTS: Coloca estas líneas al inicio del archivo app.py.
# ======================================================
from flask import Flask, render_template, request, redirect, url_for, flash, session
import json
import pandas as pd
import plotly.express as px
from database import get_db_connection
from datetime import datetime

# Importar Flask-Login
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin

# ======================================================
# INICIALIZACIÓN DE LA APLICACIÓN
# ======================================================
app = Flask(__name__)
app.secret_key = "tu_clave_secreta"  # Necesaria para usar flash y sesiones

# ======================================================
# CONFIGURACIÓN DE FLASK-LOGIN
# ======================================================
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Usuario de ejemplo en memoria (para pruebas)
users = {
    "fpuentem1": {"password": "Ar1$t0t3l3$"}
}

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    if user_id in users:
        return User(user_id)
    return None

# Antes de cada petición, forzamos la autenticación (excepto para 'login' y 'static')
@app.before_request
def require_login():
    if request.endpoint not in ['login', 'static'] and not current_user.is_authenticated:
        return redirect(url_for('login'))

# ======================================================
# FILTRO PERSONALIZADO: Formatea números con comas y sin decimales.
# ======================================================
@app.template_filter('comma')
def comma_filter(value):
    try:
        return "{:,.0f}".format(float(value))
    except (ValueError, TypeError):
        return value

# ======================================================
# FUNCIONES DE CONFIGURACIÓN: Cargar y guardar parámetros.
# ======================================================
def load_config():
    """Carga la configuración desde config.json. Si no existe, retorna valores por defecto."""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {
            "risk_threshold": 60,
            "target_exposure": {"Acciones": 40, "Bonos": 30, "Inmuebles": 20, "Otros": 10},
            "current_strategy": "Conservador"
        }
    return config

def save_config(config):
    """Guarda la configuración en config.json."""
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)

from functools import wraps
from flask import session  

def portfolio_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'portfolio_id' not in session or session['portfolio_id'] == 'default':
            flash("Debe seleccionar un portafolio antes de continuar.", "warning")
            return redirect(url_for('portfolios'))
        return f(*args, **kwargs)
    return decorated_function

# ======================================================
# FUNCIONES AUXILIARES: Obtener tipo de cambio y normalizar montos.
# ======================================================
def get_exchange_rate(month):
    """
    Obtiene el tipo de cambio (pesos por 1 dólar) para el mes dado desde la tabla exchange_rate.
    Retorna 1 si no se encuentra.
    """
    month = month.strip()
    conn = get_db_connection()
    row = conn.execute('SELECT rate FROM exchange_rate WHERE month = ?', (month,)).fetchone()
    conn.close()
    rate = row['rate'] if row else 1
    print(f"[DEBUG] Tipo de cambio para {month}: {rate}")
    return rate

def normalize_to_mxn(row):
    """
    Convierte el monto a pesos (MXN).
    Si la moneda es USD, multiplica el monto por el tipo de cambio.
    Si la moneda es MXN, devuelve el monto sin cambios.
    """
    if row['currency'] == 'USD':
        rate = get_exchange_rate(row['month'])
        converted = row['amount'] * rate if rate and rate != 0 else row['amount']
        print(f"[DEBUG] Convirtiendo: {row['amount']} USD * {rate} = {converted} MXN")
        return converted
    else:
        return row['amount']

def normalize_to_usd(row):
    """
    Convierte el monto a dólares (USD).
    Si la moneda es MXN, divide el monto por el tipo de cambio.
    Si la moneda es USD, devuelve el monto sin cambios.
    """
    if row['currency'] == 'MXN':
        rate = get_exchange_rate(row['month'])
        converted = row['amount'] / rate if rate and rate != 0 else row['amount']
        print(f"[DEBUG] Convirtiendo: {row['amount']} MXN / {rate} = {converted} USD")
        return converted
    else:
        return row['amount']

# ======================================================
# RUTAS DE LA APLICACIÓN
# ======================================================

# Endpoint de Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in users and users[username]['password'] == password:
            user = User(username)
            login_user(user)
            flash("Has iniciado sesión correctamente.", "success")
            return redirect(url_for('assets_list'))  # Redirige al listado de activos
        else:
            flash("Credenciales incorrectas. Inténtalo de nuevo.", "danger")
    return render_template('login.html')

# Endpoint de Logout
@app.route('/logout')
def logout():
    logout_user()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return redirect(url_for('assets_list'))

# Ingreso de activos (incluye campo "observaciones")
@app.route('/assets', methods=['GET', 'POST'])
@login_required
@portfolio_required
def assets():
    if request.method == 'POST':
        asset_name = request.form.get('asset_name')
        location = request.form.get('location')
        try:
            amount = float(request.form.get('amount'))
        except (ValueError, TypeError):
            flash("El monto debe ser numérico.", "warning")
            return redirect(url_for('assets'))
        currency = request.form.get('currency')
        month = request.form.get('month')
        class_id = request.form.get('class_id')
        subclass_id = request.form.get('subclass_id')
        observaciones = request.form.get('observaciones', "")
        # Usar solo año-mes para la fecha de ingreso
        fecha_ingreso = datetime.now().strftime("%Y-%m")
        portfolio_id = session.get('portfolio_id', 'default')
        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO assets (asset_name, location, amount, currency, month, clase, observaciones, fecha_ingreso, portfolio_id, class_id, subclass_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (asset_name, location, amount, currency, month, "", observaciones, fecha_ingreso, portfolio_id, class_id, subclass_id)
            )
            conn.commit()
        except Exception as e:
            flash("Error al insertar activo: " + str(e), "danger")
            return redirect(url_for('assets'))

        finally:
            conn.close()
        return redirect(url_for('assets'))
    else:
        # Rama GET: obtener las clases para el dropdown
        conn = get_db_connection()
        classes = conn.execute("SELECT * FROM classes").fetchall()
        conn.close()
        return render_template('assets.html', classes=classes)
    
# Listado de activos
@app.route('/assets/list')
@login_required
@portfolio_required
def assets_list():
    portfolio_id = session.get('portfolio_id', 'default')
    conn = get_db_connection()
    assets = conn.execute("""
        SELECT 
            a.*,
            c.name  AS class_name,
            sc.name AS subclass_name,
            st.name AS status_name
        FROM assets a
        LEFT JOIN classes    c  ON a.class_id    = c.id
        LEFT JOIN subclasses sc ON a.subclass_id = sc.id
        LEFT JOIN statuses   st ON a.estado      = st.id
        WHERE a.portfolio_id = ?
        ORDER BY a.id
    """, (portfolio_id,)).fetchall()
    conn.close()
    return render_template('assets_list.html', assets=assets)

# NUEVO ENDPOINT: Actualizar activos del mes actual.
@app.route('/assets/update_current', methods=['GET', 'POST'])
@login_required
@portfolio_required
def update_current():
    current_month = datetime.now().strftime("%Y-%m")
    conn = get_db_connection()
    if request.method == 'POST':
        assets = conn.execute("SELECT id FROM assets WHERE month = ? AND portfolio_id = ?", (current_month, session.get('portfolio_id', 'default'))).fetchall()
        for asset in assets:
            new_amount = request.form.get(f"amount_{asset['id']}")
            if new_amount:
                try:
                    new_amount = float(new_amount)
                    conn.execute("UPDATE assets SET amount = ? WHERE id = ?", (new_amount, asset['id']))
                except ValueError:
                    pass
        conn.commit()
        conn.close()
        flash("Valores actualizados para el mes actual.", "success")
        return redirect(url_for('assets_list'))
    else:
        assets = conn.execute("SELECT * FROM assets WHERE month = ? AND portfolio_id = ? AND (observaciones IS NULL OR observaciones = '')",
                                (current_month, session.get('portfolio_id', 'default'))).fetchall()
        conn.close()
        return render_template('update_current.html', assets=assets, current_month=current_month)

# Edición de activo (incluye campo "observaciones" con opción para eliminar)
@app.route('/assets/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@portfolio_required
def edit_asset(id):
    conn = get_db_connection()
    asset = conn.execute('SELECT * FROM assets WHERE id = ?', (id,)).fetchone()
    if asset is None:
        conn.close()
        return "Asset not found", 404

    if request.method == 'POST':
        asset_name = request.form.get('asset_name')
        location = request.form.get('location')
        amount = float(request.form.get('amount'))
        currency = request.form.get('currency')
        month = request.form.get('month')
        clase = request.form.get('clase')
        observaciones = request.form.get('observaciones', "")
        estado = request.form.get('estado', "activo")  # Nuevo: se lee el estado desde el formulario

        conn.execute(
            'UPDATE assets SET asset_name = ?, location = ?, amount = ?, currency = ?, month = ?, clase = ?, observaciones = ?, estado = ? WHERE id = ?',
            (asset_name, location, amount, currency, month, clase, observaciones, estado, id)
        )
        flash("Activo actualizado.", "success")
        conn.commit()
        conn.close()
        return redirect(url_for('assets_list'))

    conn.close()
    return render_template('edit_asset.html', asset=asset)

# Eliminación de activo (con confirmación)
@app.route('/assets/delete/<int:id>', methods=['POST'])
@login_required
def delete_asset(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM assets WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Activo eliminado definitivamente.", "danger")
    return redirect(url_for('assets_list'))

# ------------------------------------------------------------------
# Copiar activos de un mes a otro con validación de selección
# ------------------------------------------------------------------
@app.route('/assets/copy', methods=['GET', 'POST'])
@login_required
@portfolio_required
def copy_assets():
    source_month = datetime.now().strftime("%Y-%m")
    default_new_month = source_month  
    current_portfolio_id = session.get('portfolio_id', 'default')

    conn = get_db_connection()
    if request.method == 'POST':
        new_month = request.form.get('new_month').strip()
        selected_assets = request.form.getlist('asset_ids')
        for asset_id in selected_assets:
            asset = conn.execute("SELECT * FROM assets WHERE id = ? AND portfolio_id = ?", (asset_id, current_portfolio_id)).fetchone()
            if asset:
                new_fecha = datetime.now().strftime("%Y-%m")
                conn.execute(
                    'INSERT INTO assets (asset_name, location, amount, currency, month, clase, observaciones, fecha_ingreso, portfolio_id, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (asset['asset_name'], asset['location'], asset['amount'], asset['currency'], new_month, asset['clase'], asset['observaciones'], new_fecha, asset['portfolio_id'], asset['estado'])
                )
        conn.commit()
        conn.close()
        flash("Proceso de copia completado correctamente para el mes " + new_month, "success")
        return redirect(url_for('assets_list'))
    else:
        assets = conn.execute(
            "SELECT * FROM assets WHERE month = ? AND portfolio_id = ?",
            (source_month, current_portfolio_id)
        ).fetchall()
        conn.close()
        return render_template('copy_assets.html', assets=assets, prev_month=source_month, default_new_month=default_new_month)

# Reporte de activos: Distribución por moneda.
@app.route('/assets/report')
@login_required
def assets_report():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM assets", conn)
    conn.close()
    if df.empty:
        chart_html = "<p>No hay datos para mostrar.</p>"
    else:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df_grouped = df.groupby('currency')['amount'].sum().reset_index()
        fig = px.pie(df_grouped, values='amount', names='currency', title="Distribución de Activos por Moneda")
        chart_html = fig.to_html(full_html=False)
    return render_template('assets_report.html', chart_html=chart_html)

# Evolución de activos: Por mes y clase, normalizando a MXN.
@app.route('/assets/evolution')
@login_required
def assets_evolution():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM assets", conn)
    conn.close()
    if df.empty:
        chart_html = "<p>No hay datos para mostrar.</p>"
    else:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df['clase'] = df['clase'].fillna('Unknown')
        df['valor_normalizado'] = df.apply(normalize_to_mxn, axis=1)
        df_grouped = df.groupby(['month', 'clase'])['valor_normalizado'].sum().reset_index()
        fig = px.bar(df_grouped, x='month', y='valor_normalizado', color='clase', barmode='group',
                     title="Evolución de Activos por Mes y Clase")
        total_value = df['valor_normalizado'].sum()
        fig.update_layout(title=f"Evolución de Activos (Total: ${total_value:,.0f} MXN)",
                          yaxis=dict(tickformat=",.0f"))
        chart_html = fig.to_html(full_html=False)
    return render_template('assets_evolution.html', chart_html=chart_html)

# Crecimiento Mensual: Variación porcentual mes a mes (MXN).
@app.route('/assets/monthly_growth')
@login_required
def monthly_growth():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM assets", conn)
    conn.close()
    if df.empty:
        chart_html = "<p>No hay datos para mostrar.</p>"
    else:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df['mxn_value'] = df.apply(normalize_to_mxn, axis=1)
        df_monthly = df.groupby('month')['mxn_value'].sum().reset_index()
        df_monthly = df_monthly.sort_values('month')
        df_monthly['growth'] = df_monthly['mxn_value'].pct_change() * 100
        fig = px.line(df_monthly, x='month', y='growth', markers=True, 
                      title="Crecimiento Porcentual Mensual (MXN)")
        fig.update_yaxes(tickformat=",.0f")
        chart_html = fig.to_html(full_html=False)
    return render_template('monthly_growth.html', chart_html=chart_html)

# Comparación de Exposición por Clase: Totales, porcentajes y desviación respecto a objetivos (MXN).
@app.route('/assets/class_comparison')
@login_required
def assets_class_comparison():
    config = load_config()
    target_exposure = config.get("target_exposure", {})
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM assets", conn)
    conn.close()
    if df.empty:
        return render_template('assets_class_comparison.html', comparison=[], total_portfolio=0)
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    df['clase'] = df['clase'].fillna('Unknown')
    df['mxn_value'] = df.apply(normalize_to_mxn, axis=1)
    total_portfolio = df['mxn_value'].sum()
    df_grouped = df.groupby('clase')['mxn_value'].sum().reset_index()
    df_grouped['percentage'] = (df_grouped['mxn_value'] / total_portfolio) * 100
    comparison = []
    for _, row in df_grouped.iterrows():
        comparison.append({
            'clase': row['clase'],
            'value': row['mxn_value'],
            'percentage': row['percentage'],
            'target': target_exposure.get(row['clase'], None),
            'deviation': (row['percentage'] - target_exposure.get(row['clase'], 0)) if target_exposure.get(row['clase']) is not None else None
        })
    return render_template('assets_class_comparison.html', comparison=comparison, total_portfolio=total_portfolio)

# HISTÓRICO DE ACTIVOS: Tabla pivote con valores normalizados a USD (principal) y totales/variaciones en USD y MXN.
@app.route('/assets/history_view')
@login_required
def assets_history_view():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM assets", conn)
    conn.close()
    if df.empty:
        table_html = "<p>No hay datos históricos para mostrar.</p>"
    else:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df['usd_value'] = df.apply(lambda row: row['amount'] if row['currency'] == 'USD'
                                    else row['amount'] / get_exchange_rate(row['month']), axis=1)
        df['mxn_value'] = df.apply(lambda row: row['amount'] if row['currency'] == 'MXN'
                                    else row['amount'] * get_exchange_rate(row['month']), axis=1)
        months = sorted(df['month'].unique())
        exchange_rates = {m: get_exchange_rate(m) for m in months}
        totals_usd = {m: df[df['month'] == m]['usd_value'].sum() for m in months}
        totals_mxn = {m: df[df['month'] == m]['mxn_value'].sum() for m in months}
        pivot = df.pivot_table(index='asset_name', columns='month', values='usd_value', aggfunc='sum')
        pivot = pivot.fillna("")
        html = "<table class='table table-bordered'>"
        html += "<tr><th>Activo</th>"
        for m in months:
            html += f"<th>{m}</th>"
        html += "</tr>"
        html += "<tr><th>Tipo de Cambio</th>"
        for m in months:
            html += f"<th>TC: {exchange_rates[m]}</th>"
        html += "</tr>"
        for asset in pivot.index:
            html += f"<tr><td>{asset}</td>"
            for m in months:
                val = pivot.loc[asset].get(m, "")
                if val != "" and not pd.isna(val):
                    val_str = "${:,.0f}".format(val)
                else:
                    val_str = ""
                html += f"<td>{val_str}</td>"
            html += "</tr>"
        html += "<tr><td><strong>Total (USD)</strong></td>"
        for m in months:
            html += f"<td><strong>${totals_usd[m]:,.0f}</strong></td>"
        html += "</tr>"
        html += "<tr><td><strong>Total (MXN)</strong></td>"
        for m in months:
            html += f"<td><strong>${totals_mxn[m]:,.0f}</strong></td>"
        html += "</tr>"
        variation_usd_pct = {}
        variation_mxn_pct = {}
        for i, m in enumerate(months):
            if i == 0:
                variation_usd_pct[m] = ""
                variation_mxn_pct[m] = ""
            else:
                prev = months[i-1]
                variation_usd_pct[m] = ((totals_usd[m] - totals_usd[prev]) / totals_usd[prev]) * 100 if totals_usd[prev] != 0 else 0
                variation_mxn_pct[m] = ((totals_mxn[m] - totals_mxn[prev]) / totals_mxn[prev]) * 100 if totals_mxn[prev] != 0 else 0
        html += "<tr><td><strong>Variación (%) (USD)</strong></td>"
        for m in months:
            var = variation_usd_pct[m]
            if var == "":
                var_str = ""
            else:
                var_str = "{:,.0f}%".format(var)
                if var < 0:
                    var_str = f'<span style="color:red">{var_str}</span>'
                elif var > 0:
                    var_str = f'<span style="color:green">{var_str}</span>'
            html += f"<td>{var_str}</td>"
        html += "</tr>"
        html += "<tr><td><strong>Variación (%) (MXN)</strong></td>"
        for m in months:
            var = variation_mxn_pct[m]
            if var == "":
                var_str = ""
            else:
                var_str = "{:,.0f}%".format(var)
                if var < 0:
                    var_str = f'<span style="color:red">{var_str}</span>'
                elif var > 0:
                    var_str = f'<span style="color:green">{var_str}</span>'
            html += f"<td>{var_str}</td>"
        html += "</tr>"
        
        html += "</table>"
        table_html = html
    return render_template('assets_history.html', table_html=table_html)

# Análisis AI: Sugerencias basadas en la distribución por clase.
@app.route('/assets/ai')
@login_required
def assets_ai():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM assets", conn)
    conn.close()
    config = load_config()
    threshold = config.get("risk_threshold", 60)
    if df.empty:
        suggestions = "No hay datos disponibles para el análisis."
    else:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df['clase'] = df['clase'].fillna('Unknown')
        total_amount = df['amount'].sum()
        grouped = df.groupby('clase')['amount'].sum().reset_index()
        grouped['percentage'] = (grouped['amount'] / total_amount) * 100
        suggestions_list = []
        for index, row in grouped.iterrows():
            if row['percentage'] > threshold:
                suggestions_list.append(
                    f"Tu portafolio tiene {row['percentage']:.0f}% en la clase {row['clase']}. Considera reequilibrar tu cartera."
                )
        if not suggestions_list:
            suggestions_list.append("La distribución de tu portafolio se ve balanceada.")
        suggestions = "<br>".join(suggestions_list)
    return render_template('assets_ai.html', suggestions=suggestions)

# Configuración AI: Permite ajustar el umbral de riesgo y objetivos de exposición.
@app.route('/assets/ai/config', methods=['GET', 'POST'])
@login_required
def ai_config():
    config = load_config()
    message = None
    if request.method == 'POST':
        new_threshold = request.form.get('risk_threshold')
        try:
            new_threshold = int(new_threshold)
            config['risk_threshold'] = new_threshold
        except ValueError:
            message = "Por favor, ingresa un número válido para el umbral."
        target_exposure = {}
        for clase in ["Acciones", "Bonos", "Inmuebles", "Otros"]:
            value = request.form.get(clase)
            try:
                target_exposure[clase] = int(value)
            except (ValueError, TypeError):
                target_exposure[clase] = config.get("target_exposure", {}).get(clase, 0)
        config['target_exposure'] = target_exposure
        save_config(config)
        message = "Configuración actualizada correctamente."
    return render_template('ai_config.html', config=config, message=message)

# Tipo de Cambio Global: Permite actualizar el tipo de cambio para un mes.
@app.route('/exchange_rate', methods=['GET', 'POST'])
@login_required
def exchange_rate():
    if request.method == 'POST':
        month = request.form.get('month').strip()
        rate = request.form.get('rate')
        try:
            rate = float(rate)
        except ValueError:
            rate = 1
        conn = get_db_connection()
        existing = conn.execute('SELECT * FROM exchange_rate WHERE month = ?', (month,)).fetchone()
        if existing:
            conn.execute('UPDATE exchange_rate SET rate = ? WHERE month = ?', (rate, month))
        else:
            conn.execute('INSERT INTO exchange_rate (month, rate) VALUES (?, ?)', (month, rate))
        conn.commit()
        conn.close()
        return redirect(url_for('exchange_rate'))
    return render_template('exchange_rate.html')

# Help Page
@app.route('/help')
@login_required
def help_page():
    return render_template('help.html')

# ------------------------------------------------------------------
# ENDPOINTS PARA GESTIÓN DE PORTAFOLIOS
# ------------------------------------------------------------------
@app.route('/portfolios')
@login_required
def portfolios():
    conn = get_db_connection()
    portfolios = conn.execute('SELECT * FROM portfolios').fetchall()
    conn.close()
    return render_template('portfolios.html', portfolios=portfolios)

@app.route('/portfolios/create', methods=['GET', 'POST'])
@login_required
def create_portfolio():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            conn = get_db_connection()
            try:
                conn.execute('INSERT INTO portfolios (name) VALUES (?)', (name,))
                conn.commit()
                flash("Portafolio creado exitosamente.", "success")
            except Exception as e:
                flash("Error al crear el portafolio: " + str(e), "danger")
            finally:
                conn.close()
            return redirect(url_for('portfolios'))
        else:
            flash("El nombre del portafolio es obligatorio.", "warning")
    return render_template('create_portfolio.html')

@app.route('/portfolios/select/<int:portfolio_id>')
@login_required
def select_portfolio(portfolio_id):
    session['portfolio_id'] = portfolio_id
    flash("Portafolio seleccionado.", "success")
    return redirect(url_for('assets_list'))

# ==================================================================
# CONTEXT PROCESSOR: Inyectar el nombre del portafolio actual en todas las plantillas
# ==================================================================
@app.context_processor
def inject_portfolio():
    portfolio_id = session.get('portfolio_id', 'default')
    name = "Default"
    conn = get_db_connection()
    row = conn.execute('SELECT name FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
    conn.close()
    if row is not None:
        name = row['name']
    return {'current_portfolio_name': name}

import json
from flask import jsonify

# Endpoint para obtener las clases (Tipos de Activo)
@app.route('/api/classes')
def api_classes():
    conn = get_db_connection()
    classes = conn.execute("SELECT * FROM classes").fetchall()
    conn.close()
    # Convertir los resultados a lista de diccionarios
    classes_list = [dict(row) for row in classes]
    return jsonify(classes_list)

# Endpoint para obtener las subclases según una clase dada
@app.route('/api/subclasses/<int:class_id>')
def api_subclasses(class_id):
    conn = get_db_connection()
    subclasses = conn.execute("SELECT * FROM subclasses WHERE class_id = ?", (class_id,)).fetchall()
    conn.close()
    subclasses_list = [dict(row) for row in subclasses]
    return jsonify(subclasses_list)

# ==================================================================
# ENDPOINTS PARA CONFIGURACIÓN DE CATÁLOGOS
# ==================================================================

# Página principal del módulo de configuración de catálogos
@app.route('/config/catalogs')
@login_required
def config_catalogs():
    return render_template('config_catalogs.html')

# Configuración de Clases
@app.route('/config/clases', methods=['GET', 'POST'])
@login_required
def config_clases():
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            conn.execute("INSERT INTO classes (name) VALUES (?)", (name,))
            conn.commit()
            flash("Clase creada exitosamente.", "success")
        else:
            flash("El nombre de la clase es obligatorio.", "warning")
        conn.close()
        return redirect(url_for('config_clases'))
    else:
        classes = conn.execute("SELECT * FROM classes").fetchall()
        subclasses = conn.execute("SELECT * FROM subclasses").fetchall()
        conn.close()
        return render_template('config_clases.html', classes=classes)

# Editar una clase
@app.route('/config/clases/edit/<int:class_id>', methods=['GET', 'POST'])
@login_required
def edit_clase(class_id):
    conn = get_db_connection()
    clase = conn.execute("SELECT * FROM classes WHERE id = ?", (class_id,)).fetchone()
    if clase is None:
        conn.close()
        flash("Clase no encontrada.", "danger")
        return redirect(url_for('config_clases'))
    
    if request.method == 'POST':
        new_name = request.form.get('name')
        if not new_name:
            flash("El nombre no puede estar vacío.", "warning")
        else:
            conn.execute("UPDATE classes SET name = ? WHERE id = ?", (new_name, class_id))
            conn.commit()
            flash("Clase actualizada exitosamente.", "success")
        conn.close()
        return redirect(url_for('config_clases'))
    conn.close()
    return render_template('edit_clase.html', clase=clase)

# Eliminar una clase
@app.route('/config/clases/delete/<int:class_id>', methods=['POST'])
@login_required
def delete_clase(class_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM classes WHERE id = ?", (class_id,))
    conn.commit()
    conn.close()
    flash("Clase eliminada.", "warning")
    return redirect(url_for('config_clases'))

# Configuración de Subclases
@app.route('/config/subclasses', methods=['GET', 'POST'])
@login_required
def config_subclasses():
    conn = get_db_connection()
    if request.method == 'POST':
        class_id = request.form.get('class_id')
        name = request.form.get('name')
        if class_id and name:
            conn.execute("INSERT INTO subclasses (class_id, name) VALUES (?, ?)", (class_id, name))
            conn.commit()
            flash("Subclase creada exitosamente.", "success")
        else:
            flash("Debe seleccionar una clase y escribir el nombre de la subclase.", "warning")
        conn.close()
        return redirect(url_for('config_subclasses'))
    else:
        # Para el formulario, se listan todas las clases
        classes = conn = get_db_connection()
        classes = conn.execute("SELECT * FROM classes").fetchall()
        subclasses = conn.execute("SELECT * FROM subclasses").fetchall()
        conn.close()
        return render_template('config_subclasses.html', classes=classes, subclasses=subclasses)

# Editar una subclase
@app.route('/config/subclasses/edit/<int:subclass_id>', methods=['GET', 'POST'])
@login_required
def edit_subclass(subclass_id):
    conn = get_db_connection()
    # 1. Carga la subclase a editar
    subclass = conn.execute("SELECT * FROM subclasses WHERE id = ?", (subclass_id,)).fetchone()
    if subclass is None:
        conn.close()
        flash("Subclase no encontrada.", "danger")
        return redirect(url_for('config_subclasses'))

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_class_id = request.form.get('class_id')
        if not new_name or not new_class_id:
            flash("Todos los campos son obligatorios.", "warning")
        else:
            conn.execute(
                "UPDATE subclasses SET name = ?, class_id = ? WHERE id = ?",
                (new_name, new_class_id, subclass_id)
            )
            conn.commit()
            flash("Subclase actualizada exitosamente.", "success")
            conn.close()
            return redirect(url_for('config_subclasses'))
    
    # 2. Si es GET (o POST con error), necesitamos la lista de clases para el dropdown
    classes = conn.execute("SELECT * FROM classes").fetchall()
    conn.close()
    return render_template('edit_subclass.html', subclass=subclass, classes=classes)

# Eliminar una subclase
@app.route('/config/subclasses/delete/<int:subclass_id>', methods=['POST'])
@login_required
def delete_subclass(subclass_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM subclasses WHERE id = ?", (subclass_id,))
    conn.commit()
    conn.close()
    flash("Subclase eliminada.", "warning")
    return redirect(url_for('config_subclasses'))


# Configuración de Estatus
@app.route('/config/statuses', methods=['GET', 'POST'])
@login_required
def config_statuses():
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            conn.execute("INSERT INTO statuses (name) VALUES (?)", (name,))
            conn.commit()
            flash("Estatus agregado exitosamente.", "success")
        else:
            flash("El nombre del estatus es obligatorio.", "warning")
        conn.close()
        return redirect(url_for('config_statuses'))
    else:
        statuses = conn.execute("SELECT * FROM statuses").fetchall()
        conn.close()
        return render_template('config_statuses.html', statuses=statuses)
    
    # Editar un estatus
@app.route('/config/statuses/edit/<int:status_id>', methods=['GET', 'POST'])
@login_required
def edit_status(status_id):
    conn = get_db_connection()
    status = conn.execute("SELECT * FROM statuses WHERE id = ?", (status_id,)).fetchone()
    if status is None:
        conn.close()
        flash("Estatus no encontrado.", "danger")
        return redirect(url_for('config_statuses'))
    
    if request.method == 'POST':
        new_name = request.form.get('name')
        if not new_name:
            flash("El nombre no puede estar vacío.", "warning")
        else:
            conn.execute("UPDATE statuses SET name = ? WHERE id = ?", (new_name, status_id))
            conn.commit()
            flash("Estatus actualizado exitosamente.", "success")
        conn.close()
        return redirect(url_for('config_statuses'))
    conn.close()
    return render_template('edit_status.html', status=status)

# Eliminar un estatus
@app.route('/config/statuses/delete/<int:status_id>', methods=['POST'])
@login_required
def delete_status(status_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM statuses WHERE id = ?", (status_id,))
    conn.commit()
    conn.close()
    flash("Estatus eliminado.", "warning")
    return redirect(url_for('config_statuses'))
    
# ======================================================
# BLOQUE FINAL: Inicia la APLICACIÓN.
# ======================================================
if __name__ == '__main__':
    app.run(debug=True)