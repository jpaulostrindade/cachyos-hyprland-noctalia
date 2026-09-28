"""Local, transactional theme profiles for Noctalia 5 and Hyprland Lua."""
from __future__ import annotations
import copy, fcntl, hashlib, json, os, re, shutil, subprocess, tempfile, time, tomllib
from pathlib import Path

HOME = Path.home()
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config'))
DATA = Path(os.environ.get('XDG_DATA_HOME', HOME / '.local/share')) / 'noctalia-temas'
STATE = Path(os.environ.get('XDG_STATE_HOME', HOME / '.local/state')) / 'noctalia-temas'
NCONFIG = Path(os.environ.get('NOCTALIA_CONFIG_HOME', CONFIG)) / 'noctalia'
NSTATE = Path(os.environ.get('NOCTALIA_STATE_HOME', os.environ.get('XDG_STATE_HOME', HOME / '.local/state'))) / 'noctalia'
SETTINGS = NSTATE / 'settings.toml'
HYPR = CONFIG / 'hypr/temas.lua'
MISSING = {'__absent__': True}
COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')
IMAGES = {'.jpg', '.jpeg', '.png', '.webp', '.avif'}
BASE_HYPR = {'gaps_in':5,'gaps_out':20,'border_size':2,'rounding':10,'active_opacity':1.0,'inactive_opacity':1.0,'blur_size':5,'blur_passes':2,'shadow_range':4,'animations':True}
STYLES = {
 'equilibrado': {'label':'Equilibrado', 'hypr':BASE_HYPR, 'bar':{'position':'top','thickness':36,'margin_edge':8,'margin_ends':60,'radius':14,'background_opacity':0.94},'radius':1.0,'panel':'glass'},
 'minimal': {'label':'Minimal', 'hypr':dict(BASE_HYPR,gaps_in=3,gaps_out=8,border_size=1,rounding=5,blur_size=3,shadow_range=3),'bar':{'position':'top','thickness':30,'margin_edge':0,'margin_ends':0,'radius':0,'background_opacity':1.0},'radius':0.5,'panel':'solid'},
 'imersivo': {'label':'Imersivo', 'hypr':dict(BASE_HYPR,gaps_in=7,gaps_out=22,rounding=18,blur_size=7,blur_passes=3,shadow_range=12),'bar':{'position':'top','thickness':38,'margin_edge':10,'margin_ends':100,'radius':18,'background_opacity':0.86},'radius':1.3,'panel':'glass'},
}

def run(*args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout or 'Comando falhou: '+args[0]).strip())
    return p.stdout.strip()

def atomic(path, data, expected=None):
    path = Path(path).resolve()  # preserve symlink itself
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = data.encode() if isinstance(data,str) else data
    fd, name = tempfile.mkstemp(prefix='.'+path.name+'.', dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
        if path.exists(): os.chmod(name,path.stat().st_mode & 0o777)
        if expected is not None and (path.read_bytes() if path.exists() else b'') != expected:
            raise RuntimeError('A configuração mudou entretanto. Tenta novamente.')
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)

def jsave(path, value): atomic(path,json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def jread(path, default=None): return json.loads(path.read_text()) if path.exists() else copy.deepcopy(default)

def toml_value(v):
    if isinstance(v,bool): return 'true' if v else 'false'
    if isinstance(v,str): return json.dumps(v,ensure_ascii=False)
    if isinstance(v,(float,int)): return repr(v)
    if isinstance(v,list): return '['+', '.join(toml_value(x) for x in v)+']'
    if isinstance(v,dict): return '{'+', '.join(json.dumps(k)+' = '+toml_value(x) for k,x in v.items())+'}'
    if hasattr(v,'isoformat'): return v.isoformat()
    raise ValueError(f'Valor TOML não suportado: {type(v)}')

def dumps(v):
    # Normal section layout, preserving all values, including tables in arrays.
    lines=[]
    def section(d, path):
        if path: lines.extend(['','['+'.'.join(json.dumps(p) for p in path)+']'])
        for k,x in d.items():
            if not isinstance(x,dict): lines.append(json.dumps(k)+' = '+toml_value(x))
        for k,x in d.items():
            if isinstance(x,dict): section(x,path+[k])
    section(v,[])
    result='\n'.join(lines)+'\n'
    assert tomllib.loads(result)==v
    return result

def get(d,path):
    for part in path:
        if not isinstance(d,dict) or part not in d: return copy.deepcopy(MISSING)
        d=d[part]
    return copy.deepcopy(d)

def put(d,path,value):
    p=d
    for part in path[:-1]: p=p.setdefault(part,{})
    if value==MISSING:
        p.pop(path[-1],None)
        # Prune empty tables created for missing leaves.
        for n in range(len(path)-1,0,-1):
            parent=d
            for part in path[:n-1]: parent=parent[part]
            if parent.get(path[n-1])=={}: parent.pop(path[n-1])
    else: p[path[-1]]=copy.deepcopy(value)

def effective(): return tomllib.loads(run('noctalia','config','export','full'))
def slug(s): return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')[:60] or 'tema'
def ident(s):
    if not re.fullmatch('[a-z0-9][a-z0-9-]{0,90}',s): raise ValueError('Identificador de tema inválido')
    return s

def contrast_text(bg):
    c=[int(bg[i:i+2],16)/255 for i in (1,3,5)]
    lum=sum(a*((v/12.92) if v<=0.04045 else ((v+0.055)/1.055)**2.4) for a,v in zip((.2126,.7152,.0722),c))
    return '#101114' if (lum+.05)/.05 >= 1.05/(lum+.05) else '#ffffff'

def aether_palette(c):
    for key in ('background','foreground','accent','red','green','yellow','blue','magenta','cyan'):
        if not COLOR.fullmatch(c.get(key,'')): raise ValueError('Cor Aether inválida: '+key)
    bg,fg,ac=c['background'],c['foreground'],c['accent']
    val=lambda k,default: c.get(k,default) if COLOR.fullmatch(c.get(k,default)) else default
    v={'mPrimary':ac,'mOnPrimary':contrast_text(ac),'mSecondary':c['cyan'],'mOnSecondary':contrast_text(c['cyan']),'mTertiary':c['magenta'],'mOnTertiary':contrast_text(c['magenta']),'mError':c['red'],'mOnError':contrast_text(c['red']),'mSurface':bg,'mOnSurface':fg,'mSurfaceVariant':val('lighter_background',bg),'mOnSurfaceVariant':fg,'mOutline':val('muted',fg),'mShadow':val('darker_background',bg),'mHover':val('selection',bg),'mOnHover':fg}
    v['terminal']={'background':bg,'foreground':fg,'cursor':fg,'cursorText':bg,'selectionBg':val('selection',ac),'selectionFg':fg,'normal':{'black':bg,'white':fg},'bright':{'black':val('muted',bg),'white':val('bright_foreground',fg)}}
    for k in ['red','green','yellow','blue','magenta','cyan']:
        v['terminal']['normal'][k]=c[k]; v['terminal']['bright'][k]=val('bright_'+k,c[k])
    return {c.get('mode','dark') if c.get('mode') in ('dark','light') else 'dark':v}

def lua_profile(h):
    if set(h)!=set(BASE_HYPR): raise ValueError('Perfil Hyprland incompleto')
    for k,v in h.items():
        if k=='animations':
            if not isinstance(v,bool): raise ValueError(k)
        elif not isinstance(v,(int,float)) or isinstance(v,bool) or not 0<=v<=100: raise ValueError(k)
    for k in ['active_opacity','inactive_opacity']:
        if not .5<=h[k]<=1: raise ValueError(k)
    return '''-- Gerado pelo gestor Temas.\nhl.config({
 general = {gaps_in = %(gaps_in)s, gaps_out = %(gaps_out)s, border_size = %(border_size)s},
 decoration = {rounding = %(rounding)s, active_opacity = %(active_opacity)s, inactive_opacity = %(inactive_opacity)s,
 blur = {enabled = true, size = %(blur_size)s, passes = %(blur_passes)s}, shadow = {enabled = true, range = %(shadow_range)s}},
 animations = {enabled = %(animations)s}
})\n''' % dict(h,animations=str(h['animations']).lower())

def icon_themes(all_installed=False):
    roots=[DATA.parent/'icons', HOME/'.icons']
    roots += [Path(p)/'icons' for p in os.environ.get('XDG_DATA_DIRS','/usr/local/share:/usr/share').split(':')]
    names=set()
    for root in roots:
        for path in root.glob('*' if all_installed else 'Adwaita*'):
            if (path/'index.theme').is_file(): names.add(path.name)
    return sorted(names,key=lambda name:(name!='Adwaita',name.casefold()))

def icon_files():
    result=[(CONFIG/'gtk-3.0/settings.ini','Settings','gtk-icon-theme-name'),(CONFIG/'gtk-4.0/settings.ini','Settings','gtk-icon-theme-name')]
    for version in ['5','6']:
        path=CONFIG/('qt'+version+'ct')/('qt'+version+'ct.conf')
        if path.exists(): result.append((path,'Appearance','icon_theme'))
    return result

def ini_get(path,section,key):
    import configparser
    parser=configparser.ConfigParser(interpolation=None,strict=False); parser.optionxform=str
    if path.exists(): parser.read_string(path.read_text())
    return parser.get(section,key,fallback=None)

def ini_set(path,section,key,value,existed=True):
    raw=path.read_bytes() if path.exists() else b''
    lines=raw.decode().splitlines(keepends=True); result=[]; inside=False; found=False; section_seen=False
    for line in lines:
        m=re.match(r'^\s*\[([^]]+)\]',line)
        if m:
            if inside and not found and value is not None: result.append(key+'='+value+'\n');found=True
            inside=m.group(1)==section;section_seen=section_seen or inside
        if inside and re.match(r'^\s*'+re.escape(key)+r'\s*=',line):
            if value is not None and not found:result.append(key+'='+value+'\n')
            found=True
        else:result.append(line)
    if not found and value is not None:
        if result and not result[-1].endswith('\n'):result[-1]+='\n'
        if not section_seen:result.append('['+section+']\n')
        result.append(key+'='+value+'\n')
    text=''.join(result)
    if not existed and value is None and text.strip() in ('','['+section+']'):
        if path.exists():path.unlink()
    elif text!=raw.decode():atomic(path,text,expected=raw)

def restore_icons(state):
    set_icons(state['user'],restore=True)
    for item in state.get('files',[]):
        ini_set(Path(item['path']),item['section'],item['key'],item['value'],item['existed'])

def icon_setting():
    from gi.repository import Gio
    settings=Gio.Settings.new('org.gnome.desktop.interface')
    user=settings.get_user_value('icon-theme')
    return {'user':user.unpack() if user is not None else None,'effective':settings.get_string('icon-theme'),'files':[{'path':str(p),'section':sec,'key':key,'value':ini_get(p,sec,key),'existed':p.exists()} for p,sec,key in icon_files()]}

def set_icons(name, restore=False):
    from gi.repository import Gio
    if not restore and name not in icon_themes(all_installed=True): raise ValueError('Tema de ícones não instalado: '+str(name))
    settings=Gio.Settings.new('org.gnome.desktop.interface')
    if not settings.is_writable('icon-theme'): raise RuntimeError('A definição de ícones não permite alterações.')
    if name is None: settings.reset('icon-theme')
    elif not settings.set_string('icon-theme',name): raise RuntimeError('Não foi possível aplicar os ícones.')
    Gio.Settings.sync()
    if not restore:
        for path,section,key in icon_files():ini_set(path,section,key,name)
    if name is not None and settings.get_string('icon-theme')!=name: raise RuntimeError('O tema de ícones não foi aplicado.')

def profiles():
    result=[]
    for p in sorted((DATA/'themes').glob('*/theme.json')):
        try:
            t=jread(p); validate(t); result.append(t)
        except (ValueError,KeyError,OSError) as e: print(f'Ignorado {p}: {e}')
    return sorted(result,key=lambda t:(t['id']!='original',t['name'].casefold()))

def validate(t):
    ident(t['id'])
    if t.get('icon_theme') and t['icon_theme'] not in icon_themes(all_installed=True): raise ValueError('Tema de ícones não instalado: '+t['icon_theme'])
    if t.get('version')!=1: raise ValueError('Versão do tema não suportada')
    if not Path(t['wallpaper']).is_file(): raise ValueError('Wallpaper não encontrado: '+t['wallpaper'])
    lua_profile(t['hypr'])
    if t['source'] not in ('builtin','custom','wallpaper','community'): raise ValueError('Fonte de paleta inválida')
    if t['mode'] not in ('dark','light','auto'): raise ValueError('Modo inválido')
    if t['source']=='custom':
        pal=t['palette']
        for v in pal.values():
            for k in ['mPrimary','mSurface','mOnSurface']:
                if not COLOR.fullmatch(v.get(k,'')): raise ValueError('Paleta inválida')
    # No imported shell commands or arbitrary config keys are accepted.
    allowed={('shell','corner_radius_scale'),('shell','panel','transparency_mode'),('shell','animation','enabled'),('shell','animation','speed')}
    allowed.update(('bar','default',k) for k in ['position','thickness','margin_edge','margin_ends','radius','background_opacity','start','center','end'])
    allowed.update(('dock',k) for k in ['radius','background_opacity','icon_size'])
    if any(tuple(x['path']) not in allowed for x in t['appearance']): raise ValueError('Campo de aparência não permitido')

def appearance(style):
    s=STYLES[style]
    out=[{'path':['bar','default',k],'value':v} for k,v in s['bar'].items()]
    out += [{'path':['shell','corner_radius_scale'],'value':s['radius']},{'path':['shell','panel','transparency_mode'],'value':s['panel']},{'path':['shell','animation','enabled'],'value':True},{'path':['shell','animation','speed'],'value':1.0},{'path':['dock','radius'],'value':s['hypr']['rounding']},{'path':['dock','background_opacity'],'value':s['bar']['background_opacity']},{'path':['dock','icon_size'],'value':36 if style=='minimal' else 40}]
    return out

def save_profile(t, wallpaper=None):
    folder=DATA/'themes'/ident(t['id']); folder.mkdir(parents=True,exist_ok=True)
    if wallpaper:
        source=Path(wallpaper); digest=hashlib.sha256(source.read_bytes()).hexdigest()[:16]
        target=folder/('wallpaper-'+digest+source.suffix.lower())
        if source.resolve()!=target.resolve(): shutil.copy2(source,target)
        t['wallpaper']=str(target)
    validate(t); jsave(folder/'theme.json',t)
    return t

def import_aether(folder=None, apply_current=False):
    folders=[Path(folder)] if folder else sorted((CONFIG/'aether/themes').glob('*'))
    total=0
    for f in folders:
        if not (f/'colors.toml').exists(): continue
        pics=sorted(p for p in (f/'backgrounds').glob('*') if p.suffix.lower() in IMAGES)
        if not pics: continue
        c=tomllib.loads((f/'colors.toml').read_text())
        digest=hashlib.sha256(pics[0].read_bytes()).hexdigest()
        source=f
        if f.name=='theme':
            matches=[]
            for candidate in sorted((CONFIG/'aether/themes').glob('*')):
                for image in (candidate/'backgrounds').glob('*'):
                    if image.is_file() and image.suffix.lower() in IMAGES and hashlib.sha256(image.read_bytes()).hexdigest()==digest:
                        matches.append(candidate); break
            if len(matches)==1: source=matches[0]
        key='aether-'+slug(source.name if source.name!='theme' else pics[0].stem)
        # Reuse legacy entries created from a filename, including after a source rename.
        old={}
        candidates=['aether-'+slug(pics[0].stem),key]
        for candidate in candidates:
            old=jread(DATA/'themes'/candidate/'theme.json',{})
            if old: key=candidate; break
        if not old:
            for candidate in profiles():
                if candidate.get('origin')=='Aether' and candidate.get('style')=='equilibrado':
                    match=candidate.get('aether_wallpaper_hash')==digest
                    if not match: match=hashlib.sha256(Path(candidate['wallpaper']).read_bytes()).hexdigest()==digest
                    if match: old=candidate; key=candidate['id']; break
        name=old.get('name','')
        autogenerated=not name or name=='Theme' or name.startswith('Paisagem ')
        source_changed=old.get('aether_source') and old['aether_source']!=source.name
        if not old.get('name_locked') and source.name!='theme' and (autogenerated or source_changed or not old):
            name=source.name
        elif autogenerated:
            name=pics[0].stem.replace('-desktop-wallpaper','').replace('-',' ').title()
            if name.isdigit(): name='Paisagem '+name[-4:]
        if source.name=='refugio-na-bruma' and not old.get('name_locked'): name='Refúgio na bruma'
        t={'version':1,'id':key,'name':name,'description':'Paleta original do Aether · perfil Equilibrado','source':'custom','selection':key,'mode':c.get('mode','dark'),'palette':aether_palette(c),'appearance':old.get('appearance',appearance('equilibrado')),'hypr':old.get('hypr',copy.deepcopy(BASE_HYPR)),'style':'equilibrado','origin':'Aether','aether_source':source.name,'aether_wallpaper_hash':digest,'name_locked':old.get('name_locked',False)}
        if old.get('icon_theme'): t['icon_theme']=old['icon_theme']
        save_profile(t,pics[0]); total+=1
    if apply_current:
        if not total: raise RuntimeError('O Aether ainda não gerou um tema válido.')
        return apply(key)
    return total

def current_hypr():
    h=copy.deepcopy(BASE_HYPR)
    keys={'gaps_in':'general:gaps_in','gaps_out':'general:gaps_out','border_size':'general:border_size','rounding':'decoration:rounding','active_opacity':'decoration:active_opacity','inactive_opacity':'decoration:inactive_opacity','blur_size':'decoration:blur:size','blur_passes':'decoration:blur:passes','shadow_range':'decoration:shadow:range','animations':'animations:enabled'}
    for k,path in keys.items():
        v=json.loads(run('hyprctl','-j','getoption',path))
        if 'int' in v: value=v['int']
        elif 'float' in v: value=v['float']
        elif 'bool' in v: value=v['bool']
        elif 'css' in v:
            values=[float(n) for n in v['css'].split()]
            if len(set(values))!=1: raise RuntimeError('Margens assimétricas: é necessário guardar os quatro valores.')
            value=values[0]
        elif 'custom' in v: value=float(str(v['custom']).split()[0])
        else: raise RuntimeError('Não consegui ler '+path)
        h[k]=bool(value) if k=='animations' else value
    return h

def capture(name='Ambiente original', key=None):
    cfg=effective(); key=key or slug(name)+'-'+str(int(time.time()))
    th=cfg['theme']; source=th['source']; selection=th.get({'builtin':'builtin','custom':'custom_palette','community':'community_palette','wallpaper':'wallpaper_scheme'}[source],'')
    t={'version':1,'id':key,'name':name,'description':'Ambiente guardado · wallpaper, paleta e aparência','source':source,'selection':selection,'mode':th['mode'],'appearance':[{'path':x['path'],'value':get(cfg,x['path'])} for x in appearance('equilibrado')], 'hypr':current_hypr(),'origin':'Guardado','style':'guardado'}
    t['icon_theme']=icon_setting()['effective']
    # Keep existing non-Adwaita themes when saving the current desktop too.
    for part in ['start','center','end']:
        t['appearance'].append({'path':['bar','default',part],'value':get(cfg,['bar','default',part])})
    if source=='custom': t['palette']=jread(NCONFIG/'palettes'/(selection+'.json'))
    return save_profile(t,run('noctalia','msg','wallpaper-get'))

class Transaction:
    def __enter__(self):
        STATE.mkdir(parents=True,exist_ok=True)
        self.f=open(STATE/'lock','a')
        try: fcntl.flock(self.f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: self.f.close(); raise RuntimeError('Já existe uma mudança de tema em curso.')
        return self
    def __exit__(self,*args): self.f.close()

def pending(): return jread(STATE/'pending.json')
def history(): return jread(STATE/'history.json',[])
def active(): return jread(STATE/'active.json',{})

def edit_settings(changes):
    raw=SETTINGS.read_bytes() if SETTINGS.exists() else b''
    d=tomllib.loads(raw.decode())
    for x in changes: put(d,x['path'],x['value'])
    text=dumps(d)
    # Validate isolated content before touching live config.
    with tempfile.TemporaryDirectory(prefix='temas-check-') as f:
        p=Path(f)/'settings.toml'; p.write_text(text)
        validation=run('noctalia','config','validate',str(p))
        if 'WARN' in validation: raise RuntimeError(validation)
    atomic(SETTINGS,text,expected=raw)

def wait_for(check, message, seconds=18):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if check(): return
        time.sleep(.3)
    raise RuntimeError(message)

def palette_selection(t):
    if t['source']!='custom': return t['selection']
    digest=hashlib.sha256(json.dumps(t['palette'],sort_keys=True).encode()).hexdigest()[:12]
    return 'temas-'+t['id']+'-'+digest

def primary_color():
    p=CONFIG/'hypr/noctalia.lua'
    m=re.search(r'local primary = "rgb\(([0-9a-fA-F]{6})\)"',p.read_text()) if p.exists() else None
    return m.group(1).lower() if m else None

def reload_verify(t=None, expected_primary=None):
    run('noctalia','msg','config-reload')
    if t:
        expected=t['source']+' '+palette_selection(t)
        wait_for(lambda: run('noctalia','msg','color-scheme-get')==expected,'Noctalia não confirmou a paleta.')
        wait_for(lambda: run('noctalia','msg','wallpaper-get')==t['wallpaper'],'Noctalia não confirmou o wallpaper.')
    run('noctalia','msg','templates-apply')
    if t and t['source']=='custom':
        v=t['palette'].get(t['mode'],next(iter(t['palette'].values())))
        needle=v['mPrimary'].lstrip('#').lower()
        wait_for(lambda: needle in (CONFIG/'hypr/noctalia.lua').read_text().lower(),'As cores do Hyprland não foram geradas.')
    if expected_primary:
        wait_for(lambda: primary_color()==expected_primary,'A paleta anterior ainda não foi regenerada.')
    run('hyprctl','reload')
    color=primary_color()
    if color:
        border=json.loads(run('hyprctl','-j','getoption','general:col.active_border')).get('gradient','').lower()
        if color not in border: raise RuntimeError('A borda do Hyprland não coincide com a paleta.')
    err=run('hyprctl','configerrors')
    if err.strip(): raise RuntimeError('Hyprland: '+err)

def restore_snapshot(snap):
    # Restore only leaves owned by this operation, keeping unrelated settings.
    if 'icons_before' in snap: restore_icons(snap['icons_before'])
    edit_settings(snap['before'])
    atomic(HYPR,snap['hypr_before'] or '-- Sem perfil adicional.\n')
    jsave(STATE/'active.json',snap['active_before'])
    reload_verify(expected_primary=snap.get('primary_before'))

def apply(key):
    with Transaction():
        if pending(): raise RuntimeError('Há uma operação interrompida. Usa Restaurar anterior primeiro.')
        t=jread(DATA/'themes'/ident(key)/'theme.json'); validate(t)
        run('noctalia','msg','color-scheme-get')
        errors=run('hyprctl','configerrors')
        if errors.strip(): raise RuntimeError('Resolve primeiro os erros atuais do Hyprland: '+errors)
        cfg=effective()
        if not cfg.get('theme',{}).get('templates',{}).get('enable_builtin_templates') or 'hyprland' not in cfg['theme']['templates'].get('builtin_ids',[]):
            raise RuntimeError('Ativa os modelos integrados de cores do Hyprland nas definições do Noctalia.')
        changes=copy.deepcopy(t['appearance'])
        selection=palette_selection(t)
        for path,v in [(('theme','source'),t['source']),(('theme','mode'),t['mode']),(('theme','shell_mode'),'follow'),(('theme','pure_black_dark'),False),(('theme',{'builtin':'builtin','custom':'custom_palette','community':'community_palette','wallpaper':'wallpaper_scheme'}[t['source']]),selection),(('wallpaper','default','path'),t['wallpaper']),(('wallpaper','last','path'),t['wallpaper']),(('wallpaper','automation','enabled'),False)]: changes.append({'path':list(path),'value':v})
        monitors=set(cfg.get('wallpaper',{}).get('monitors',{}))
        monitors.update(m['name'] for m in json.loads(run('hyprctl','-j','monitors')))
        for m in monitors: changes.append({'path':['wallpaper','monitors',m,'path'],'value':t['wallpaper']})
        original=tomllib.loads(SETTINGS.read_text()) if SETTINGS.exists() else {}
        snap={'time':time.time(),'target':key,'primary_before':primary_color(),'before':[{'path':x['path'],'value':get(original,x['path'])} for x in changes],'hypr_before':HYPR.read_text() if HYPR.exists() else None,'active_before':active()}
        if t.get('icon_theme'): snap['icons_before']=icon_setting()
        backup=STATE/'backups'/str(time.time_ns()); backup.mkdir(parents=True)
        if SETTINGS.exists(): shutil.copy2(SETTINGS,backup/'settings.toml')
        jsave(backup/'transaction.json',snap)
        jsave(STATE/'pending.json',snap)
        try:
            if t['source']=='custom': jsave(NCONFIG/'palettes'/(selection+'.json'),t['palette'])
            atomic(HYPR,lua_profile(t['hypr']))
            edit_settings(changes)
            reload_verify(t)
            if t.get('icon_theme'): set_icons(t['icon_theme'])
            jsave(STATE/'active.json',{'id':key,'name':t['name'],'applied_at':time.time()})
            hs=history(); hs.append(snap); jsave(STATE/'history.json',hs)
            (STATE/'pending.json').unlink()
        except Exception as original_error:
            try: restore_snapshot(snap); (STATE/'pending.json').unlink()
            except Exception as restore_error: raise RuntimeError(f'{original_error}\nRestauro pendente: {restore_error}') from original_error
            raise RuntimeError(f'{original_error}\nO ambiente anterior foi reposto.') from original_error
    return t['name']

def undo():
    with Transaction():
        hs=history(); p=pending(); s=p or (hs[-1] if hs else None)
        if not s: raise RuntimeError('Ainda não há uma mudança para restaurar.')
        restore_snapshot(s)
        if p: (STATE/'pending.json').unlink()
        else: hs.pop(); jsave(STATE/'history.json',hs)
    return 'Ambiente anterior restaurado'
