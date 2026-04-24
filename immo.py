import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import re
import hashlib
import time

# Configuration de la page
st.set_page_config(
    page_title="ImmoVision - Gestion Immobilière",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Style CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    * { font-family: 'Inter', sans-serif; }
    
    [data-testid="stSidebar"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding-top: 2rem;
    }
    [data-testid="stSidebar"] * { color: white !important; }
    
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 20px;
        color: white;
        transition: transform 0.3s;
    }
    .metric-card:hover { transform: translateY(-5px); }
    .metric-card .value { font-size: 2.5rem; font-weight: 700; margin: 0.5rem 0; }
    
    .stButton button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 500;
        transition: all 0.3s;
    }
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 20px rgba(102,126,234,0.4);
    }
    
    .login-container {
        max-width: 450px;
        margin: auto;
        padding: 2rem;
        background: white;
        border-radius: 30px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Configuration base de données
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'database': 'gestion_immobiliere',
    'user': 'root',
    'password': '123456789'
}

# Fonction de connexion
def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        st.error(f"Erreur de connexion: {err}")
        return None

# Initialisation de la base de données
def init_database():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        
        # Table users simple (sans vérification email)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    return False

# Hashage du mot de passe
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Inscription simple
def register_user(email, password):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        hashed_pwd = hash_password(password)
        
        try:
            cursor.execute("INSERT INTO users (email, password) VALUES (%s, %s)", (email, hashed_pwd))
            conn.commit()
            return True, "Compte créé avec succès!"
        except mysql.connector.IntegrityError:
            return False, "Cet email est déjà utilisé"
        finally:
            cursor.close()
            conn.close()
    return False, "Erreur de connexion"

# Connexion simple
def authenticate(email, password):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        hashed_pwd = hash_password(password)
        cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, hashed_pwd))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user
    return None

# Fonctions de gestion des données
def get_all_bureaux():
    conn = get_db_connection()
    if conn:
        query = """
        SELECT b.*, COALESCE(SUM(p.montant), 0) as total_paye
        FROM bureaux b
        LEFT JOIN paiements p ON b.id_bureau = p.id_bureau
        GROUP BY b.id_bureau
        ORDER BY b.id_bureau
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    return pd.DataFrame()

def get_revenus_mensuels():
    conn = get_db_connection()
    if conn:
        query = """
        SELECT DATE_FORMAT(mois, '%%Y-%%m') as mois, SUM(montant) as total
        FROM paiements
        GROUP BY DATE_FORMAT(mois, '%%Y-%%m')
        ORDER BY mois DESC LIMIT 12
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    return pd.DataFrame()

def get_revenus_annuels():
    conn = get_db_connection()
    if conn:
        query = """
        SELECT YEAR(mois) as annee, SUM(montant) as total
        FROM paiements
        GROUP BY YEAR(mois)
        ORDER BY annee DESC
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    return pd.DataFrame()

def get_total_charges():
    conn = get_db_connection()
    if conn:
        query = "SELECT COALESCE(SUM(montant), 0) as total FROM charges"
        df = pd.read_sql(query, conn)
        conn.close()
        return df['total'].iloc[0] if not df.empty else 0
    return 0

def get_paiements_en_retard():
    conn = get_db_connection()
    if conn:
        query = """
        SELECT b.nom, b.id_bureau, COALESCE(MAX(p.mois), '2024-01-01') as dernier_paiement,
        b.loyer as loyer_mensuel
        FROM bureaux b
        LEFT JOIN paiements p ON b.id_bureau = p.id_bureau
        GROUP BY b.id_bureau
        HAVING dernier_paiement < DATE_SUB(CURDATE(), INTERVAL 1 MONTH) AND b.loyer > 0
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    return pd.DataFrame()

def add_paiement(id_bureau, mois, montant, id_contrat):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO paiements (id_bureau, mois, montant, id_contrat)
                VALUES (%s, %s, %s, %s)
            """, (id_bureau, mois, montant, id_contrat))
            conn.commit()
            return True
        except Exception as e:
            st.error(f"Erreur: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    return False

def add_charge(id_bureau, categorie, montant, mois):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO charges (id_bureau, categorie, montant, mois)
                VALUES (%s, %s, %s, %s)
            """, (id_bureau, categorie, montant, mois))
            conn.commit()
            return True
        except Exception as e:
            st.error(f"Erreur: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    return False

def add_contrat(id_bureau, date_debut, date_fin, loyer_ht, loyer_ttc, commentaires):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO contrats (id_bureau, date_debut, date_fin, loyer_ht, loyer_ttc, commentaires)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (id_bureau, date_debut, date_fin, loyer_ht, loyer_ttc, commentaires))
            conn.commit()
            return True
        except Exception as e:
            st.error(f"Erreur: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    return False

def add_locataire(nom, telephone):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO locataires (nom, telephone) VALUES (%s, %s)", (nom, telephone))
            conn.commit()
            return True
        except Exception as e:
            st.error(f"Erreur: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    return False

# Interface de connexion/inscription simple
def login_interface():
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   -webkit-background-clip: text; 
                   -webkit-text-fill-color: transparent; 
                   font-size: 3rem;">
            🏢 ImmoVision
        </h1>
        <p style="color: #666;">Solution avancée de gestion immobilière</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["🔐 Connexion", "📝 Inscription"])
        
        # Connexion
        with tab1:
            email = st.text_input("Email", key="login_email", placeholder="votre@email.com")
            password = st.text_input("Mot de passe", type="password", key="login_password", placeholder="Votre mot de passe")
            
            if st.button("Se connecter", use_container_width=True, key="login_btn"):
                if email and password:
                    user = authenticate(email, password)
                    if user:
                        st.session_state['authenticated'] = True
                        st.session_state['user_email'] = email
                        st.rerun()
                    else:
                        st.error("Email ou mot de passe incorrect")
                else:
                    st.warning("Veuillez remplir tous les champs")
        
        # Inscription simple
        with tab2:
            email_reg = st.text_input("Email", key="reg_email", placeholder="votre@email.com")
            password_reg = st.text_input("Mot de passe", type="password", key="reg_password", placeholder="Minimum 6 caractères")
            confirm_password = st.text_input("Confirmer le mot de passe", type="password", key="confirm_password")
            
            if st.button("S'inscrire", use_container_width=True, key="register_btn"):
                if email_reg and password_reg and confirm_password:
                    if not re.match(r"[^@]+@[^@]+\.[^@]+", email_reg):
                        st.error("Email invalide")
                    elif password_reg != confirm_password:
                        st.error("Les mots de passe ne correspondent pas")
                    elif len(password_reg) < 6:
                        st.error("Le mot de passe doit contenir au moins 6 caractères")
                    else:
                        success, message = register_user(email_reg, password_reg)
                        if success:
                            st.success("✅ Compte créé avec succès! Vous pouvez maintenant vous connecter.")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(message)
                else:
                    st.warning("Veuillez remplir tous les champs")
        
        st.markdown('</div>', unsafe_allow_html=True)

# Dashboard principal
def main_dashboard():
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
        <h1 style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   -webkit-background-clip: text; 
                   -webkit-text-fill-color: transparent;">
            🏢 ImmoVision Dashboard
        </h1>
        <div style="display: flex; gap: 1rem;">
            <span>👤 {st.session_state.get('user_email', '')}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown("# 🏢 ImmoVision")
        st.markdown("---")
        menu = st.radio("📋 Menu", [
            "📊 Tableau de bord",
            "🏢 Bureaux",
            "💰 Paiements",
            "📄 Contrats",
            "🔄 Charges",
            "👥 Locataires"
        ])
        
        st.markdown("---")
        if st.button("🚪 Déconnexion", use_container_width=True):
            st.session_state['authenticated'] = False
            st.rerun()
    
    if menu == "📊 Tableau de bord":
        bureaux_df = get_all_bureaux()
        revenus_mensuels = get_revenus_mensuels()
        revenus_annuels = get_revenus_annuels()
        total_charges = get_total_charges()
        paiements_retard = get_paiements_en_retard()
        
        col1, col2, col3, col4 = st.columns(4)
        
        total_mensuel = revenus_mensuels['total'].iloc[0] if not revenus_mensuels.empty else 0
        total_annuel = revenus_annuels['total'].iloc[0] if not revenus_annuels.empty else 0
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <h3>🏢 Total Bureaux</h3>
                <div class="value">{len(bureaux_df)}</div>
                <small>Bureaux en gestion</small>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <h3>💰 Revenus Mensuels</h3>
                <div class="value">{total_mensuel:,.0f} DH</div>
                <small>Mois en cours</small>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <h3>📈 Revenus Annuels</h3>
                <div class="value">{total_annuel:,.0f} DH</div>
                <small>Année en cours</small>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <h3>🔧 Total Charges</h3>
                <div class="value">{total_charges:,.0f} DH</div>
                <small>Total</small>
            </div>
            """, unsafe_allow_html=True)
        
        # Graphiques
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Revenus Mensuels")
            if not revenus_mensuels.empty:
                fig = px.bar(revenus_mensuels, x='mois', y='total', title="Évolution des revenus mensuels",
                            color_discrete_sequence=['#667eea'])
                fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune donnée de paiement disponible")
        
        with col2:
            st.subheader("📈 Revenus Annuels")
            if not revenus_annuels.empty:
                fig = px.line(revenus_annuels, x='annee', y='total', title="Évolution des revenus annuels",
                             markers=True, color_discrete_sequence=['#764ba2'])
                fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune donnée annuelle disponible")
        
        # Paiements en retard
        st.subheader("⚠️ Paiements en retard")
        if not paiements_retard.empty:
            st.dataframe(paiements_retard, use_container_width=True)
        else:
            st.success("✅ Tous les paiements sont à jour!")
        
        # Distribution des loyers
        st.subheader("💰 Distribution des loyers par bureau")
        bureaux_avec_loyer = bureaux_df[bureaux_df['loyer'] > 0][['nom', 'loyer']]
        if not bureaux_avec_loyer.empty:
            fig = px.pie(bureaux_avec_loyer, values='loyer', names='nom', title="Répartition des loyers",
                        color_discrete_sequence=px.colors.sequential.Purples_r)
            st.plotly_chart(fig, use_container_width=True)
    
    elif menu == "🏢 Bureaux":
        st.subheader("🏢 Liste des bureaux")
        bureaux_df = get_all_bureaux()
        
        if not bureaux_df.empty:
            col1, col2 = st.columns(2)
            with col1:
                etage_filter = st.multiselect("Filtrer par étage", 
                                             options=bureaux_df['etage'].unique().tolist())
            with col2:
                specialite_filter = st.multiselect("Filtrer par spécialité", 
                                                  options=bureaux_df['specialite'].unique().tolist())
            
            bureaux_filtered = bureaux_df.copy()
            if etage_filter:
                bureaux_filtered = bureaux_filtered[bureaux_filtered['etage'].isin(etage_filter)]
            if specialite_filter:
                bureaux_filtered = bureaux_filtered[bureaux_filtered['specialite'].isin(specialite_filter)]
            
            st.dataframe(bureaux_filtered[['id_bureau', 'nom', 'specialite', 'etage', 'code', 'loyer', 'total_paye']], 
                        use_container_width=True)
        else:
            st.info("Aucun bureau trouvé")
    
    elif menu == "💰 Paiements":
        st.subheader("💰 Gestion des paiements")
        
        tab1, tab2 = st.tabs(["📝 Enregistrer un paiement", "📊 Historique des paiements"])
        
        with tab1:
            bureaux_df = get_all_bureaux()
            if not bureaux_df.empty:
                bureau_options = bureaux_df[bureaux_df['loyer'] > 0][['id_bureau', 'nom']]
                if not bureau_options.empty:
                    col1, col2 = st.columns(2)
                    with col1:
                        selected_bureau = st.selectbox("Bureau", 
                                                      options=bureau_options['id_bureau'].tolist(),
                                                      format_func=lambda x: bureau_options[bureau_options['id_bureau']==x]['nom'].iloc[0])
                        mois = st.date_input("Mois du paiement", value=date.today())
                        montant = st.number_input("Montant (DH)", min_value=0.0, step=1000.0)
                        id_contrat = st.number_input("ID Contrat", min_value=1, step=1, value=1)
                        
                        if st.button("💾 Enregistrer le paiement", use_container_width=True):
                            if montant > 0:
                                if add_paiement(selected_bureau, mois, montant, id_contrat):
                                    st.success("✅ Paiement enregistré avec succès!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Erreur lors de l'enregistrement")
                            else:
                                st.warning("Veuillez entrer un montant valide")
                else:
                    st.info("Aucun bureau avec loyer défini")
            else:
                st.info("Aucun bureau disponible")
        
        with tab2:
            conn = get_db_connection()
            if conn:
                query = """
                SELECT p.*, b.nom as bureau_nom 
                FROM paiements p
                JOIN bureaux b ON p.id_bureau = b.id_bureau
                ORDER BY p.mois DESC
                LIMIT 100
                """
                paiements_df = pd.read_sql(query, conn)
                conn.close()
                
                if not paiements_df.empty:
                    st.dataframe(paiements_df, use_container_width=True)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total des paiements", f"{paiements_df['montant'].sum():,.0f} DH")
                    with col2:
                        st.metric("Moyenne par paiement", f"{paiements_df['montant'].mean():,.0f} DH")
                    with col3:
                        st.metric("Nombre de paiements", len(paiements_df))
                else:
                    st.info("Aucun paiement enregistré")
    
    elif menu == "📄 Contrats":
        st.subheader("📄 Gestion des contrats")
        
        conn = get_db_connection()
        if conn:
            query = """
            SELECT c.*, b.nom as bureau_nom
            FROM contrats c
            JOIN bureaux b ON c.id_bureau = b.id_bureau
            ORDER BY c.date_debut DESC
            """
            contrats_df = pd.read_sql(query, conn)
            conn.close()
            
            if not contrats_df.empty:
                st.dataframe(contrats_df, use_container_width=True)
            else:
                st.info("Aucun contrat enregistré")
            
            with st.expander("➕ Ajouter un contrat"):
                bureaux_df = get_all_bureaux()
                if not bureaux_df.empty:
                    col1, col2 = st.columns(2)
                    with col1:
                        new_id_bureau = st.selectbox("Bureau", 
                                                    options=bureaux_df['id_bureau'].tolist(),
                                                    format_func=lambda x: bureaux_df[bureaux_df['id_bureau']==x]['nom'].iloc[0])
                        new_date_debut = st.date_input("Date début")
                        new_loyer_ht = st.number_input("Loyer HT", min_value=0.0, step=1000.0)
                    with col2:
                        new_date_fin = st.date_input("Date fin")
                        new_loyer_ttc = st.number_input("Loyer TTC", min_value=0.0, step=1000.0)
                        new_commentaires = st.text_area("Commentaires")
                    
                    if st.button("Créer contrat"):
                        if add_contrat(new_id_bureau, new_date_debut, new_date_fin, new_loyer_ht, new_loyer_ttc, new_commentaires):
                            st.success("✅ Contrat ajouté avec succès!")
                            time.sleep(1)
                            st.rerun()
                else:
                    st.warning("Aucun bureau disponible")
    
    elif menu == "🔄 Charges":
        st.subheader("🔄 Gestion des charges")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### ➕ Ajouter une charge")
            bureaux_df = get_all_bureaux()
            if not bureaux_df.empty:
                bureau_charge = st.selectbox("Bureau", 
                                            options=bureaux_df['id_bureau'].tolist(),
                                            format_func=lambda x: bureaux_df[bureaux_df['id_bureau']==x]['nom'].iloc[0],
                                            key="charge_bureau")
                
                categorie = st.selectbox("Catégorie", ["Électricité", "Eau", "Gaz", "Entretien", "Taxes", "Autre"])
                montant_charge = st.number_input("Montant (DH)", min_value=0.0, step=100.0)
                mois_charge = st.date_input("Mois", value=date.today())
                
                if st.button("💾 Enregistrer la charge", use_container_width=True):
                    if montant_charge > 0:
                        if add_charge(bureau_charge, categorie, montant_charge, mois_charge):
                            st.success("✅ Charge enregistrée avec succès!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Erreur lors de l'enregistrement")
                    else:
                        st.warning("Veuillez entrer un montant valide")
            else:
                st.info("Aucun bureau disponible")
        
        with col2:
            st.markdown("### 📊 Historique des charges")
            conn = get_db_connection()
            if conn:
                query = """
                SELECT ch.*, b.nom as bureau_nom
                FROM charges ch
                JOIN bureaux b ON ch.id_bureau = b.id_bureau
                ORDER BY ch.mois DESC
                LIMIT 50
                """
                charges_df = pd.read_sql(query, conn)
                conn.close()
                
                if not charges_df.empty:
                    st.dataframe(charges_df, use_container_width=True)
                    
                    charges_by_cat = charges_df.groupby('categorie')['montant'].sum().reset_index()
                    if not charges_by_cat.empty:
                        fig = px.pie(charges_by_cat, values='montant', names='categorie', title="Répartition des charges par catégorie")
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Aucune charge enregistrée")
    
    elif menu == "👥 Locataires":
        st.subheader("👥 Gestion des locataires")
        
        conn = get_db_connection()
        if conn:
            query = "SELECT * FROM locataires ORDER BY id_locataire DESC"
            locataires_df = pd.read_sql(query, conn)
            conn.close()
            
            if not locataires_df.empty:
                st.dataframe(locataires_df, use_container_width=True)
            else:
                st.info("Aucun locataire enregistré")
            
            with st.expander("➕ Ajouter un locataire"):
                col1, col2 = st.columns(2)
                with col1:
                    nom_loc = st.text_input("Nom complet")
                with col2:
                    telephone_loc = st.text_input("Téléphone")
                
                if st.button("Ajouter locataire"):
                    if nom_loc and telephone_loc:
                        if add_locataire(nom_loc, telephone_loc):
                            st.success("✅ Locataire ajouté avec succès!")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.warning("Veuillez remplir tous les champs")

# Point d'entrée principal
def main():
    if not init_database():
        st.error("Impossible de se connecter à la base de données. Vérifiez votre configuration MySQL.")
        return
    
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    
    if not st.session_state['authenticated']:
        login_interface()
    else:
        main_dashboard()

if __name__ == "__main__":
    main()