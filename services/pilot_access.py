"""First-access gate for the nonbinding pilot; never handles electoral private keys."""
import argparse
import csv
import hashlib
import hmac
from html import escape
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError
import threading
import re

ITERATIONS = 600_000
COOKIE = '__Host-theogen_pilot'
PREFIX = '/acceso'


class AccessDenied(Exception):
    pass


class NativeUnavailable(Exception):
    pass


def atomic_private_json(path, value):
    path=Path(path);temporary=path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
    with temporary.open('x',encoding='utf-8') as stream:
        os.chmod(temporary,0o600);json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)


class NativeBridge:
    """A dedicated native admin identity; credentials stay on the loopback service."""
    def __init__(self,path,transport=None,mail_path=None):
        self.path=Path(path);self.lock=threading.RLock();self.transport=transport or self.request
        self.mail_path=Path(mail_path) if mail_path else None

    @staticmethod
    def request(method,route,token=None,payload=None):
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self,*args):return None
        headers={'Content-Type':'application/json','Connection':'close'}
        if token:headers['Authorization']='Bearer '+token
        request=Request('http://127.0.0.1:18022/api/'+route,method=method,headers=headers,
                        data=None if payload is None else json.dumps(payload).encode())
        try:
            with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=10) as response:
                raw=response.read(65536)
                return response.status,json.loads(raw) if raw else None
        except HTTPError as error:return error.code,None
        except (OSError,ValueError):raise NativeUnavailable() from None

    def token(self,email):
        with self.lock:
            entries=json.loads(self.path.read_text());entry=entries.get(email)
            if entry is None:raise AccessDenied('native_identity_required')
            token=entry.get('token')
            if token and entry.get('expiration',0)>time.time()+60:
                status,account=self.transport('GET','account',token=token)
                if status==200 and account.get('id')==entry['account_id']:return token
                if status not in (401,403):raise NativeUnavailable()
            status,value=self.transport('POST','login/local',payload={'username':email,'password':entry['service_password']})
            if status!=200 or not isinstance(value.get('token') if isinstance(value,dict) else None,str):raise NativeUnavailable()
            status,account=self.transport('GET','account',token=value['token'])
            if status!=200 or account.get('id')!=entry['account_id']:raise NativeUnavailable()
            entry.update(token=value['token'],expiration=value['expiration']);atomic_private_json(self.path,entries)
            return value['token']

    def revoke(self,email,expected=None):
        with self.lock:
            entries=json.loads(self.path.read_text());entry=entries.get(email)
            if entry is None:raise AccessDenied('native_identity_required')
            token=entry.get('token')
            if expected is not None and (not token or not hmac.compare_digest(expected,token)):
                raise AccessDenied('native_session_required')
            if token:
                status,_=self.transport('DELETE','login',token=token)
                if status not in (200,401,403):raise NativeUnavailable()
            entry.update(token=None,expiration=0);atomic_private_json(self.path,entries)

    def roster(self,email):
        entries=json.loads(self.path.read_text());entry=entries[email];token=self.token(email)
        route='elections/'+entry['uuid']+'/draft'
        status,readiness=self.transport('GET',route+'/status',token=token)
        if status!=200:raise NativeUnavailable()
        status,voters=self.transport('GET',route+'/voters',token=token)
        if status!=200 or not isinstance(voters,list):raise NativeUnavailable()
        digest=hashlib.sha256(json.dumps(voters,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return entry,readiness,voters,digest

    def confirm_roster(self,email):
        with self.lock:
            entry,readiness,voters,digest=self.roster(email)
            if readiness['credentials_ready'] or readiness.get('credentials_left'):
                raise AccessDenied('credentials_already_started')
            if not 2<=len(voters)<=100 or self.mail_path is None:raise AccessDenied('invalid_roster')
            mail=json.loads(self.mail_path.read_text());recipients=[]
            for voter in voters:
                if isinstance(voter,str):
                    values=next(csv.reader([voter]));address=values[0];weight=values[2] if len(values)>2 else '1'
                elif isinstance(voter,dict):address=voter.get('address','');weight=str(voter.get('weight',1))
                else:raise AccessDenied('invalid_roster')
                if weight!='1':raise AccessDenied('unsupported_weight')
                address=mail.get('aliases',{}).get(address.lower(),address.lower())
                if not re.fullmatch(r'[^\s@,;]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}',address):raise AccessDenied('invalid_roster')
                recipients.append(address)
            if len(set(recipients))!=len(recipients):raise AccessDenied('duplicate_roster_recipient')
            operation=self.path.parent/'roster-confirmation.json'
            if operation.exists():
                prior=json.loads(operation.read_text())
                if prior.get('status')=='CONFIRMED' and prior.get('roster_sha256')==digest:return len(voters)
                raise AccessDenied('roster_confirmation_requires_reconciliation')
            with operation.open('x') as stream:
                os.chmod(operation,0o600);json.dump({'status':'INTENT','roster_sha256':digest,'count':len(voters)},stream)
                stream.flush();os.fsync(stream.fileno())
            mail['allowed_recipients']=sorted(set(entry['required_recipients'])|set(recipients))
            atomic_private_json(self.mail_path,mail)
            entries=json.loads(self.path.read_text());entries[email].update(roster_sha256=digest,roster_count=len(voters))
            atomic_private_json(self.path,entries)
            atomic_private_json(operation,{'status':'CONFIRMED','roster_sha256':digest,'count':len(voters)})
            return len(voters)

    def roster_confirmed(self):
        entries=json.loads(self.path.read_text())
        if len(entries)!=1:return False
        email,entry=next(iter(entries.items()))
        if not entry.get('roster_sha256'):return False
        _,_,_,actual=self.roster(email)
        return hmac.compare_digest(actual,entry['roster_sha256'])


class Connection(sqlite3.Connection):
    def __exit__(self, *arguments):
        try: return super().__exit__(*arguments)
        finally: self.close()


def password_hash(password, salt=None):
    salt = salt or secrets.token_urlsafe(18)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), ITERATIONS, 32).hex()
    return salt, f'{ITERATIONS}${digest}'


def password_matches(password, salt, stored):
    try:
        rounds, expected = stored.split('$')
        if not 600_000 <= int(rounds) <= 2_000_000: return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(rounds), 32).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, AttributeError): return False


def native_password_update(path, username, password):
    """Belenios 3.3.0 PBKDF2 format; preserve all unrelated native accounts."""
    path = Path(path)
    rows = list(csv.reader(io.StringIO(path.read_text(encoding='utf-8'))))
    matches = [row for row in rows if row and row[0] == username]
    if len(matches) != 1 or len(matches[0]) != 4 or matches[0][3].lower() != username:
        raise AccessDenied('native_account_mismatch')
    salt, digest = password_hash(password)
    matches[0][1:3] = [salt, digest]
    temporary = path.with_name(path.name + '.' + secrets.token_hex(8) + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8', newline='') as stream:
            os.chmod(temporary, 0o600)
            csv.writer(stream).writerows(rows); stream.flush(); os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary.exists(): temporary.unlink()


class Portal:
    def __init__(self, directory, public_base, sync=None):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.database = self.directory / 'access.sqlite'
        origin = urlsplit(public_base)
        if origin.scheme != 'https' or not origin.hostname or origin.path or origin.query or origin.fragment or origin.username:
            raise ValueError('HTTPS origin required')
        self.origin = public_base
        self.sync = sync or self.unconfigured
        key = self.directory / 'csrf_key'
        if not key.exists():
            with key.open('xb') as stream: stream.write(secrets.token_bytes(32))
            key.chmod(0o600)
        self.key = key.read_bytes()
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                  email TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
                  salt TEXT NOT NULL, digest TEXT NOT NULL, must_change INTEGER NOT NULL,
                  epoch INTEGER NOT NULL DEFAULT 0, expires REAL, target TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                  digest TEXT PRIMARY KEY, email TEXT NOT NULL, epoch INTEGER NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS failures (key TEXT NOT NULL, observed REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS failure_time ON failures(key,observed);
            ''')
        self.database.chmod(0o600)

    @staticmethod
    def unconfigured(*args):raise AccessDenied('native_admin_bridge_unconfigured')

    def connection(self):
        db = sqlite3.connect(self.database, timeout=10, factory=Connection)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON'); db.execute('PRAGMA synchronous=FULL')
        return db

    def provision(self, email, name, role, provisional, target):
        email = email.lower()
        destination = urlsplit(target)
        if (role not in ('administrator','trustee','credential_authority')
                or destination.scheme != 'https' or destination.netloc != urlsplit(self.origin).netloc
                or destination.path != {'administrator':'/admin','trustee':'/trustee','credential_authority':'/credauth'}.get(role)):
            raise ValueError('Invalid scoped target')
        salt, digest = password_hash(provisional)
        with self.connection() as db:
            db.execute('INSERT INTO users(email,name,role,salt,digest,must_change,expires,target) VALUES(?,?,?,?,?,1,?,?)',
                       (email,name,role,salt,digest,time.time()+86400,target))

    def csrf(self, token):
        return hmac.new(self.key, ('csrf:'+token).encode(), hashlib.sha256).hexdigest()

    def user(self, token, db=None):
        owned = db is None
        db = db or self.connection()
        try:
            row = db.execute('''SELECT u.*,s.expires AS session_expires FROM users u JOIN sessions s ON u.email=s.email
                WHERE s.digest=? AND s.epoch=u.epoch AND s.expires>?''',
                (hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
            if row is None or (row['must_change'] and row['expires'] <= time.time()): raise AccessDenied('session_required')
            return dict(row)
        finally:
            if owned: db.close()

    def new_session(self, db, user):
        token = secrets.token_urlsafe(32)
        expires = time.time() + (900 if user['must_change'] else 8*3600)
        db.execute('INSERT INTO sessions VALUES(?,?,?,?)',
                   (hashlib.sha256(token.encode()).hexdigest(),user['email'],user['epoch'],expires))
        return token

    def login(self, email, password, ip):
        if not isinstance(password,str) or len(password)>128: raise AccessDenied('invalid_login')
        email = email.lower().strip()
        now = time.time()
        keys = [hmac.new(self.key, label.encode(), hashlib.sha256).hexdigest() for label in ('email:'+email,'ip:'+ip)]
        db = self.connection()
        try:
            db.execute('BEGIN IMMEDIATE')
            for key in keys:
                if db.execute('SELECT COUNT(*) FROM failures WHERE key=? AND observed>?',(key,now-900)).fetchone()[0]>=5:
                    raise AccessDenied('temporarily_limited')
            user = db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
            valid = password_matches(password,user['salt'],user['digest']) if user else password_matches(password,'synthetic-dummy-salt','600000$'+'0'*64)
            if not valid or not user or (user['must_change'] and user['expires']<=now):
                db.executemany('INSERT INTO failures VALUES(?,?)',[(key,now) for key in keys]);db.commit()
                raise AccessDenied('invalid_login')
            db.executemany('DELETE FROM failures WHERE key=?',[(key,) for key in keys])
            token = self.new_session(db,user);db.commit()
            return token,bool(user['must_change'])
        finally: db.close()

    def change(self, token, csrf, password, confirmation, current=''):
        if not hmac.compare_digest(self.csrf(token),csrf): raise AccessDenied('invalid_csrf')
        if (password!=confirmation or not 12<=len(password)<=128 or password.strip()!=password
                or not any(c.islower() for c in password) or not any(c.isupper() for c in password)
                or not any(c.isdigit() for c in password)):
            raise AccessDenied('password_policy')
        db = self.connection()
        try:
            db.execute('BEGIN IMMEDIATE');user=self.user(token,db)
            if not user['must_change'] and not password_matches(current,user['salt'],user['digest']):
                raise AccessDenied('current_password_required')
            if password_matches(password,user['salt'],user['digest']): raise AccessDenied('new_password_required')
            if user['role']=='administrator': self.sync(user['email'],password)
            salt,digest=password_hash(password)
            db.execute('UPDATE users SET salt=?,digest=?,must_change=0,epoch=epoch+1,expires=NULL WHERE email=?',
                       (salt,digest,user['email']))
            db.execute('DELETE FROM sessions WHERE email=?',(user['email'],))
            user.update(must_change=0,epoch=user['epoch']+1)
            fresh=self.new_session(db,user);db.commit();return fresh
        finally: db.close()

    def logout(self, token, csrf):
        if not hmac.compare_digest(self.csrf(token),csrf): raise AccessDenied('invalid_csrf')
        with self.connection() as db:
            db.execute('DELETE FROM sessions WHERE digest=?',(hashlib.sha256(token.encode()).hexdigest(),))


def server(address, portal, bridge=None):
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self,*args): pass

        def reply(self,status,body='',location=None,token=None,clear=False,content_type='text/html; charset=utf-8'):
            data=body.encode('utf-8');self.send_response(status)
            headers={'Content-Type':content_type,'Content-Length':str(len(data)),
                'Cache-Control':'no-store','Pragma':'no-cache','Connection':'close',
                'Referrer-Policy':'same-origin','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',
                'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"}
            if location:headers['Location']=location
            if token:headers['Set-Cookie']=f'{COOKIE}={token}; Secure; HttpOnly; SameSite=Strict; Path=/'
            if clear:headers['Set-Cookie']=f'{COOKIE}=; Secure; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'
            for key,value in headers.items():self.send_header(key,value)
            self.end_headers();self.wfile.write(data);self.close_connection=True

        def token(self):
            cookie=SimpleCookie()
            try:cookie.load(self.headers.get('Cookie',''))
            except Exception:return ''
            value=cookie.get(COOKIE);return value.value if value else ''

        def page(self,title,body):
            return '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+''' · Votación CPA IAC</title>
<style>body{font:17px/1.6 system-ui;margin:0;background:#f0f5f8;color:#173047}header{background:#12344b;color:white;padding:1.6rem max(1rem,calc((100vw - 44rem)/2))}header p{margin:.2rem 0}.institution{font-size:1.3rem;font-weight:700}.demo{display:inline-block;background:#d9f2eb;color:#164a3b;border-radius:1rem;padding:.15rem .8rem;font-size:.85rem;margin-top:.6rem}main{box-sizing:border-box;background:white;max-width:44rem;margin:2rem auto;padding:2rem;border:1px solid #dce5eb;border-radius:.8rem}h1{font-size:1.6rem;line-height:1.3}label{display:block;margin:1rem 0}input,button{font:inherit;padding:.65rem;width:100%;box-sizing:border-box;border:1px solid #92a8b8;border-radius:.3rem}input[type=checkbox]{width:auto}button{background:#165f68;color:white;border:0;cursor:pointer;margin:1rem 0;font-weight:600}a{color:#155d81}input:focus-visible,button:focus-visible,a:focus-visible{outline:3px solid #d18b22;outline-offset:3px}@media(max-width:48rem){main{margin:1rem;padding:1.25rem}}</style></head><body><header><p class="institution">Votación Centro de Padres IAC</p><p>Instituto Abdón Cifuentes</p><span class="demo">Demostración no vinculante</span></header><main><h1>'''+escape(title)+'</h1>'+body+'</main></body></html>'

        def do_GET(self):
            if self.path=='/api-token':
                try:
                    user=portal.user(self.token())
                    if user['must_change'] or user['role']!='administrator' or bridge is None:raise AccessDenied()
                    return self.reply(200,bridge.token(user['email']),content_type='text/plain; charset=utf-8')
                except AccessDenied:return self.reply(403,'Acceso administrativo no habilitado')
                except (NativeUnavailable,OSError,ValueError):return self.reply(503,'Sesión nativa no confirmada')
            if self.path==PREFIX+'/salud':return self.reply(200,'ok')
            if self.path not in (PREFIX,PREFIX+'/',PREFIX+'/cambiar-clave',PREFIX+'/panel'):return self.reply(404,'No disponible')
            token=self.token()
            try:user=portal.user(token)
            except AccessDenied:user=None
            if user is None:
                return self.reply(200,self.page('Acceso a la votación',
                    '<p>Ingresa con el correo y la contraseña de acceso recibida. La primera vez debes elegir una contraseña nueva.</p>'
                    '<form method="post" action="/acceso/entrar"><label>Correo<input name="email" type="email" autocomplete="username" required></label>'
                    '<label>Contraseña<input name="password" type="password" autocomplete="current-password" maxlength="128" required></label><button>Ingresar</button></form>'
                    '<p>Este acceso no contiene tu credencial electoral ni genera tu parte privada de custodia.</p>'))
            if user['must_change'] or self.path==PREFIX+'/cambiar-clave':
                current='' if user['must_change'] else '<label>Contraseña actual<input name="current" type="password" autocomplete="current-password" maxlength="128" required></label>'
                return self.reply(200,self.page('Elige una contraseña nueva',
                    '<p>El acceso a tu función se habilitará al completar este cambio. Usa al menos 12 caracteres, con mayúscula, minúscula y número.</p>'
                    '<form method="post" action="/acceso/cambiar-clave"><input type="hidden" name="csrf" value="'+portal.csrf(token)+'">'+current+
                    '<label>Nueva contraseña<input name="password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required></label>'
                    '<label>Confirmación<input name="confirmation" type="password" autocomplete="new-password" minlength="12" maxlength="128" required></label>'
                    '<button>Guardar y continuar</button></form>'))
            roles={'administrator':'Administración','trustee':'Custodia','credential_authority':'Autoridad externa de credenciales'}
            detail=('<p>Tu sesión habilita la administración de la votación del Centro de Padres IAC. Carga y revisa el padrón CSV antes de generar las credenciales de votación.</p>' if user['role']=='administrator' else
                    '<p>Abre únicamente tu función desde tu equipo. Genera y conserva allí tu material privado.</p>')
            role_link='<p><a rel="noreferrer" href="'+escape(user['target'],quote=True)+'">Abrir mi función</a></p>'
            if user['role']=='credential_authority':
                try:ready=bridge is not None and bridge.roster_confirmed()
                except (NativeUnavailable,OSError,ValueError,AccessDenied):ready=False
                if not ready:role_link='<p>El padrón definitivo está pendiente. Espera la confirmación del administrador antes de generar credenciales.</p>'
            if user['role']=='administrator':
                detail+='<p>En la pestaña Votantes, sube el CSV UTF-8 sin encabezado: correo,identificador. Un voto por persona. Revisa la cantidad y confirma aquí el padrón antes de avisar a la autoridad de credenciales.</p>'
                detail+='<form method="post" action="/acceso/confirmar-padron"><input type="hidden" name="csrf" value="'+portal.csrf(token)+'"><label><input name="reviewed" type="checkbox" value="yes" required>Revisé el CSV definitivo y la cantidad de votantes.</label><button>Confirmar padrón definitivo</button></form>'
            return self.reply(200,self.page('Tu acceso al ensayo',
                '<p>'+escape(user['name'])+' · '+roles[user['role']]+'</p>'+detail+
                role_link+
                '<p>La credencial de votación la entrega por separado la autoridad externa. No compartas aquí tus claves privadas.</p>'
                '<p><a href="/acceso/cambiar-clave">Cambiar contraseña</a></p>'
                '<form method="post" action="/acceso/salir"><input type="hidden" name="csrf" value="'+portal.csrf(token)+'"><button>Cerrar sesión</button></form>'))

        def do_POST(self):
            if self.headers.get('Origin')!=portal.origin:return self.reply(403,'Origen no autorizado')
            self.connection.settimeout(10)
            try:
                size=int(self.headers.get('Content-Length','-1'))
                if not 0<size<=4096 or self.headers.get('Transfer-Encoding'):return self.reply(413,'Solicitud inválida')
                if self.headers.get('Content-Type','').split(';')[0]!='application/x-www-form-urlencoded':return self.reply(415,'Formato inválido')
                values=parse_qs(self.rfile.read(size).decode('utf-8'),keep_blank_values=True,max_num_fields=5)
                if any(len(v)!=1 for v in values.values()):raise AccessDenied('invalid_request')
                values={k:v[0] for k,v in values.items()}
                if self.path==PREFIX+'/entrar':
                    token,pending=portal.login(values.get('email',''),values.get('password',''),self.headers.get('X-Real-IP',self.client_address[0]))
                    return self.reply(303,location=PREFIX+('/cambiar-clave' if pending else '/panel'),token=token)
                if self.path==PREFIX+'/cambiar-clave':
                    token=portal.change(self.token(),values.get('csrf',''),values.get('password',''),values.get('confirmation',''),values.get('current',''))
                    return self.reply(303,location=PREFIX+'/panel',token=token)
                if self.path==PREFIX+'/salir':
                    if not hmac.compare_digest(portal.csrf(self.token()),values.get('csrf','')):raise AccessDenied('invalid_csrf')
                    user=portal.user(self.token())
                    if user['role']=='administrator' and bridge is not None:bridge.revoke(user['email'])
                    portal.logout(self.token(),values.get('csrf',''));return self.reply(303,location=PREFIX+'/',clear=True)
                if self.path==PREFIX+'/confirmar-padron':
                    token=self.token();user=portal.user(token)
                    if (user['must_change'] or user['role']!='administrator' or bridge is None
                            or not hmac.compare_digest(portal.csrf(token),values.get('csrf','')) or values.get('reviewed')!='yes'):
                        raise AccessDenied('roster_confirmation_forbidden')
                    bridge.confirm_roster(user['email']);return self.reply(303,location=PREFIX+'/panel')
                return self.reply(404,'No disponible')
            except AccessDenied as error:
                messages={'password_policy':'Usa dos contraseñas coincidentes de 12 a 128 caracteres, con mayúscula, minúscula y número.',
                          'new_password_required':'Elige una contraseña distinta de la actual.',
                          'temporarily_limited':'Demasiados intentos. Espera 15 minutos.'}
                return self.reply(403,self.page('No se completó la operación',
                    '<p>'+messages.get(str(error),'Revisa tus datos y vuelve a ingresar.')+'</p><a href="/acceso/">Volver al acceso</a>'))
            except (ValueError,UnicodeError,OSError,sqlite3.Error,NativeUnavailable):return self.reply(503,'La operación no se confirmó. Revisa tu sesión antes de continuar.')

        def do_DELETE(self):
            if self.path!='/api/login' or self.headers.get('Origin')!=portal.origin:return self.reply(403,'Origen no autorizado')
            try:
                token=self.token();user=portal.user(token)
                if user['must_change'] or user['role']!='administrator' or bridge is None:raise AccessDenied()
                bearer=self.headers.get('Authorization','')
                if not bearer.startswith('Bearer '):raise AccessDenied()
                bridge.revoke(user['email'],expected=bearer[7:])
                portal.logout(token,portal.csrf(token))
                return self.reply(200,'null',clear=True,content_type='application/json')
            except AccessDenied:return self.reply(403,'Sesión no autorizada')
            except (NativeUnavailable,OSError,ValueError):return self.reply(503,'Cierre de sesión no confirmado')

    instance=ThreadingHTTPServer(address,Handler);instance.daemon_threads=True;return instance


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=18445);args=parser.parse_args()
    os.umask(0o077)
    bridge=NativeBridge(os.environ['ACCESS_NATIVE_BRIDGE'],mail_path=os.environ['ACCESS_MAIL_CONFIG'])
    portal=Portal(os.environ['ACCESS_STATE_DIR'],os.environ['ACCESS_PUBLIC_BASE'],sync=lambda email,password:bridge.revoke(email))
    server(('127.0.0.1',args.port),portal,bridge).serve_forever()


if __name__=='__main__':main()
