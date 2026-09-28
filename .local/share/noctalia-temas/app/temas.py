#!/usr/bin/env python3
"""GTK4 theme catalogue; CLI operations use the same transactional backend."""
import argparse, copy, json, os, subprocess, sys, threading, time
from pathlib import Path
import theme_core as core

def cli():
    p=argparse.ArgumentParser(description='Temas integrados para Noctalia e Hyprland')
    sub=p.add_subparsers(dest='command')
    sub.add_parser('list'); sub.add_parser('undo'); sub.add_parser('aether-apply'); sub.add_parser('smoke-test')
    a=sub.add_parser('apply'); a.add_argument('id')
    a=sub.add_parser('import-aether'); a.add_argument('folder',nargs='?')
    a=sub.add_parser('save'); a.add_argument('name')
    args=p.parse_args()
    if args.command:
        try:
            if args.command=='smoke-test': return gui(smoke=True)
            if args.command=='list': print(json.dumps(core.profiles(),ensure_ascii=False,indent=2))
            elif args.command=='apply': print(core.apply(args.id))
            elif args.command=='undo': print(core.undo())
            elif args.command=='aether-apply': print(core.import_aether(core.CONFIG/'aether/theme', apply_current=True))
            elif args.command=='import-aether': print(core.import_aether(args.folder))
            elif args.command=='save': print(core.capture(args.name)['name'])
        except Exception as e: print(str(e),file=sys.stderr); return 1
        return 0
    return gui()

def gui(smoke=False):
    import gi
    gi.require_version('Gtk','4.0')
    from gi.repository import Gtk, Gdk, Gio, GLib, Pango
    GLib.set_prgname("dev.local.NoctaliaTemas")
    GLib.set_application_name("Temas")
    class App(Gtk.Application):
        def __init__(self):
            super().__init__(application_id='dev.local.NoctaliaTemas.Test' if smoke else 'dev.local.NoctaliaTemas',flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
            self.connect('activate',self.activate)
            self.busy=False; self.selected=None
        def label(self,text='',css=None):
            w=Gtk.Label(label=text,xalign=0); w.set_wrap(True)
            if css: w.add_css_class(css)
            return w
        def button(self,text,callback,css=None):
            w=Gtk.Button(label=text); w.connect('clicked',callback)
            if css: w.add_css_class(css)
            return w
        def activate(self,*_):
            if hasattr(self,'win'): self.win.present(); return
            self.win=Gtk.ApplicationWindow(application=self,title='Temas · Noctalia & Hyprland',default_width=1060,default_height=760)
            provider=Gtk.CssProvider()
            provider.load_from_string('''
              window.temas {background:#111319; color:#e8e9ee;}
              .temas .title {font-size:25px;font-weight:700;}
              .temas .subtitle {color:#9ca4b7;font-size:13px;}
              .temas .section-title {font-weight:700;font-size:16px;}
              .temas .catalog {background:#171a23;border-right:1px solid #2a3040;}
              .temas button {border-radius:10px;padding:9px 14px;}
              .temas button.suggested-action {background:#b4c5ff;color:#172344;font-weight:700;}
              .temas .theme-card {background:#1e2330;border:1px solid #2b3343;border-radius:12px;padding:9px;margin:5px 10px;}
              .temas row:selected .theme-card {border:2px solid #b4c5ff;padding:8px;}
              .temas row {padding:0;background:transparent;}
              .temas .card-name {font-size:14px;font-weight:650;margin-top:6px;}
              .temas .card-origin {font-size:11px;color:#9ca4b7;}
              .temas .preview {border-radius:14px;border:1px solid #394155;}
              .temas .mock-bar {padding:7px 12px;margin:14px 18px;border-radius:10px;font-size:11px;}
              .temas .mock-window {border-radius:12px;padding:18px;margin:55px 45px 30px;}
              .temas .mock-terminal {font-family:monospace;font-size:12px;}
              .temas .hint {color:#9ca4b7;font-size:12px;}
              .temas .status {padding:10px 16px;background:#1b2130;font-size:12px;}
              .temas .error {color:#ffb4ab;}
            ''')
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.win.set_icon_name('preferences-desktop-theme')
            self.win.add_css_class('temas')
            outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            header=Gtk.Box(spacing=12); header.set_margin_top(18); header.set_margin_bottom(18); header.set_margin_start(22); header.set_margin_end(22)
            titlebox=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3); titlebox.set_hexpand(True)
            titlebox.append(self.label('Temas','title')); titlebox.append(self.label('O teu ambiente, num só lugar.','subtitle')); header.append(titlebox)
            header.append(self.button('Importar do Aether',self.import_themes))
            header.append(self.button('Guardar ambiente',self.save_dialog))
            outer.append(header)
            body=Gtk.Box(); body.set_vexpand(True)
            side=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8); side.set_size_request(275,-1); side.add_css_class('catalog')
            self.search=Gtk.SearchEntry(placeholder_text='Pesquisar temas…'); self.search.set_margin_start(12); self.search.set_margin_end(12); self.search.set_margin_top(12)
            self.search.connect('search-changed',lambda *_: self.listbox.invalidate_filter()); side.append(self.search)
            self.listbox=Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE); self.listbox.set_filter_func(self.filter_row); self.listbox.connect('row-selected',self.select)
            sc=Gtk.ScrolledWindow(vexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER); sc.set_child(self.listbox); side.append(sc)
            aether=self.button('Explorar wallpapers no Aether',lambda *_:subprocess.Popen([str(core.HOME/'.local/bin/aether')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
            aether.set_margin_start(12); aether.set_margin_end(12); aether.set_margin_bottom(12); side.append(aether); body.append(side)
            right=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12); right.set_hexpand(True)
            for attr in ['top','bottom','start','end']: getattr(right,'set_margin_'+attr)(20)
            self.name=self.label('Escolhe um tema','title'); right.append(self.name)
            self.description=self.label('','subtitle'); right.append(self.description)
            self.preview=Gtk.Overlay(); self.preview.add_css_class('preview'); self.preview.set_size_request(550,330); self.preview.set_vexpand(True)
            self.wallpaper=Gtk.Picture(content_fit=Gtk.ContentFit.COVER,can_shrink=True); self.preview.set_child(self.wallpaper)
            mock=Gtk.Box(orientation=Gtk.Orientation.VERTICAL); mock.set_can_target(False)
            self.bar=Gtk.Box(); self.bar.add_css_class('mock-bar'); self.bar.set_valign(Gtk.Align.START)
            self.bar.append(self.label('◉   1   2   3')); spacer=Gtk.Box(hexpand=True); self.bar.append(spacer); self.bar.append(self.label('Noctalia     •     12:30')); mock.append(self.bar)
            self.terminal=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12); self.terminal.add_css_class('mock-window'); self.terminal.set_valign(Gtk.Align.CENTER); self.terminal.set_vexpand(True)
            self.terminal.append(self.label('●  ●  ●                          Terminal','section-title'))
            term=self.label('paulo@cachyos  ~\n\n❯ Um ambiente com identidade.\n\n  Wallpaper · Cores · Janelas\n  Barra · Menus · Aplicações','mock-terminal'); self.terminal.append(term)
            mock.append(self.terminal); self.preview.add_overlay(mock); right.append(self.preview)
            right.append(self.label('Pré-visualização ilustrativa do tema.','hint'))
            self.swatches=Gtk.Box(spacing=8); right.append(self.swatches)
            stylebox=Gtk.Box(spacing=12); stylebox.append(self.label('Estilo do ambiente'))
            self.styles=['guardado']+list(core.STYLES)
            self.style=Gtk.DropDown.new_from_strings(['Conforme guardado']+[v['label'] for v in core.STYLES.values()]); self.style.connect('notify::selected',self.style_changed); stylebox.append(self.style); right.append(stylebox)
            iconrow=Gtk.Box(spacing=12); iconrow.append(self.label('Ícones'))
            self.icon_names=['']+core.icon_themes()
            for profile in core.profiles():
                saved=profile.get('icon_theme')
                if saved and saved not in self.icon_names:self.icon_names.append(saved)
            self.icons=Gtk.DropDown.new_from_strings(['Manter os atuais']+self.icon_names[1:]); self.icons.connect('notify::selected',self.style_changed); iconrow.append(self.icons)
            self.icon_preview=Gtk.Box(spacing=8); iconrow.append(self.icon_preview); right.append(iconrow)
            right.append(self.label('Algumas aplicações precisam de ser reabertas para atualizar os ícones.','hint'))
            self.details=self.label('','hint'); right.append(self.details)
            actions=Gtk.Box(spacing=10); self.apply_button=self.button('Aplicar tema',self.apply_theme,'suggested-action'); actions.append(self.apply_button)
            self.undo_button=self.button('Restaurar anterior',self.restore); actions.append(self.undo_button); right.append(actions)
            body.append(right); outer.append(body)
            self.status=self.label('Pronto. Super + Alt + T abre este catálogo.','status'); outer.append(self.status)
            self.win.set_child(outer)
            self.win.connect('close-request',lambda *_: self.busy)
            self.refresh()
            if core.pending(): self.status.set_text('Uma mudança foi interrompida. Clica em Restaurar anterior para recuperar.'); self.apply_button.set_sensitive(False)
            self.win.present()
            if smoke: GLib.timeout_add(900,self.smoke_check)
        def smoke_check(self):
            count=0
            row=self.listbox.get_first_child()
            while row:
                self.listbox.select_row(row)
                for i in range(len(self.styles)):
                    self.style.set_selected(i)
                    assert self.name.get_text()
                    count+=1
                row=row.get_next_sibling()
            for i in range(len(self.icon_names)):
                self.icons.set_selected(i)
                assert self.icon_preview.get_first_child() is not None
            assert self.preview.get_width()>=500
            assert self.apply_button.get_mapped()
            print(json.dumps({'rendered_profiles_and_styles':count,'window':[self.win.get_width(),self.win.get_height()],'preview':[self.preview.get_width(),self.preview.get_height()],'actions_mapped':True}),flush=True)
            self.quit()
            return False
        def filter_row(self,row): return self.search.get_text().casefold() in (row.theme['name']+' '+row.theme.get('origin','')).casefold()
        def refresh(self,selected=None):
            while self.listbox.get_first_child(): self.listbox.remove(self.listbox.get_first_child())
            active=core.active().get('id'); pick=None
            for t in core.profiles():
                row=Gtk.ListBoxRow(); row.theme=t
                box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL); box.add_css_class('theme-card')
                pic=Gtk.Picture.new_for_filename(t['wallpaper']); pic.set_content_fit(Gtk.ContentFit.COVER); pic.set_can_shrink(True); pic.set_size_request(220,100); box.append(pic)
                box.append(self.label(t['name']+('  ✓' if active==t['id'] else ''),'card-name')); box.append(self.label(t.get('origin','Local'),'card-origin')); row.set_child(box); self.listbox.append(row)
                if t['id']==(selected or active): pick=row
            self.listbox.select_row(pick or self.listbox.get_row_at_index(0))
            self.undo_button.set_sensitive(bool(core.history() or core.pending()))
        def select(self,_,row):
            if not row: return
            self.selected=copy.deepcopy(row.theme); self.style.set_selected(0)
            saved=self.selected.get('icon_theme','')
            self.icons.set_selected(self.icon_names.index(saved) if saved in self.icon_names else 0); self.render()
        def current(self):
            t=copy.deepcopy(self.selected)
            st=self.styles[self.style.get_selected()]
            if st!='guardado':
                t['appearance']=core.appearance(st); t['hypr']=copy.deepcopy(core.STYLES[st]['hypr']); t['style']=st
                t['description']='Perfil '+core.STYLES[st]['label']+' · cores preservadas'
            icon=self.icon_names[self.icons.get_selected()]
            if icon: t['icon_theme']=icon
            else: t.pop('icon_theme',None)
            return t
        def style_changed(self,*_):
            if self.selected and hasattr(self,'icons'): self.render()
        def render(self):
            t=self.current(); self.name.set_text(t['name']); self.description.set_text(t['description']); self.wallpaper.set_filename(t['wallpaper'])
            pal=t.get('palette',{}); v=pal.get(t['mode'],next(iter(pal.values()),{})); bg=v.get('mSurface','#161a25'); fg=v.get('mOnSurface','#e1e7f4'); ac=v.get('mPrimary','#b4c5ff')
            if not hasattr(self,'preview_css'): self.preview_css=Gtk.CssProvider(); Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),self.preview_css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+1)
            # All interpolated colors pass backend validation or fixed defaults.
            bar_values={x['path'][-1]:x['value'] for x in t['appearance'] if x['path'][:2]==['bar','default']}
            bar_radius=bar_values.get('radius',12)
            self.bar.set_margin_top(int(bar_values.get('margin_edge',8)/2)+6)
            self.preview_css.load_from_string(f'.temas .mock-bar {{background:{bg};color:{fg};border-radius:{bar_radius}px;}} .temas .mock-window {{background:{bg};color:{fg};border:2px solid {ac};border-radius:{t["hypr"]["rounding"]}px;}}')
            while self.swatches.get_first_child(): self.swatches.remove(self.swatches.get_first_child())
            for k in ['mPrimary','mSecondary','mTertiary','mSurface','mOnSurface']:
                col=v.get(k,ac); dot=Gtk.Label(); dot.set_markup(f'<span foreground="{col}">●</span>'); dot.set_tooltip_text(col); self.swatches.append(dot)
            self.swatches.append(self.label('Paleta Aether preservada' if t['source']=='custom' else 'Paleta '+t['selection'],'hint'))
            while self.icon_preview.get_first_child(): self.icon_preview.remove(self.icon_preview.get_first_child())
            icon_theme=Gtk.IconTheme.new()
            icon_theme.set_search_path(Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).get_search_path())
            icon_theme.set_theme_name(t.get('icon_theme') or core.icon_setting()['effective'])
            for name in ['folder','user-home','folder-download']:
                paint=icon_theme.lookup_icon(name,None,32,1,Gtk.TextDirection.NONE,Gtk.IconLookupFlags(0))
                sample=Gtk.Image.new_from_paintable(paint); sample.set_pixel_size(32); self.icon_preview.append(sample)
            h=t['hypr']; self.details.set_text(f'Janelas: cantos {h["rounding"]:g} px · margens {h["gaps_out"]:g} px\nInclui barra, menus, dock e cores das aplicações configuradas no Noctalia.')
        def job(self,description,fn,after=None):
            if self.busy: return
            self.busy=True; self.win.get_child().get_first_child().set_sensitive(False); self.apply_button.set_sensitive(False); self.undo_button.set_sensitive(False); self.listbox.set_sensitive(False); self.style.set_sensitive(False); self.icons.set_sensitive(False)
            self.status.remove_css_class('error'); self.status.set_text(description)
            def worker():
                try: result=fn(); GLib.idle_add(done,True,str(result))
                except Exception as e: GLib.idle_add(done,False,str(e))
            def done(ok,message):
                self.busy=False; self.win.get_child().get_first_child().set_sensitive(True); self.apply_button.set_sensitive(not core.pending()); self.listbox.set_sensitive(True); self.style.set_sensitive(True); self.icons.set_sensitive(True)
                self.refresh(self.selected['id'] if self.selected else None)
                self.status.set_text(message)
                if not ok: self.status.add_css_class('error')
                if ok and after: after()
                return False
            threading.Thread(target=worker,daemon=True).start()
        def apply_theme(self,*_):
            if not self.selected: return
            t=self.current()
            variation=self.styles[self.style.get_selected()]!='guardado'
            icons_changed=t.get('icon_theme')!=self.selected.get('icon_theme')
            def action():
                # A style variation is a new profile; the original remains available.
                if variation:
                    original=t['id']; t['id']=core.slug(original+'-'+t['style']); t['name']+=' · '+core.STYLES[t['style']]['label']; core.save_profile(t)
                if icons_changed and not variation: core.save_profile(t)
                return 'Aplicado: '+core.apply(t['id'])
            self.job('A aplicar wallpaper, paleta e aparência…',action)
        def restore(self,*_): self.job('A restaurar o ambiente anterior…',core.undo)
        def import_themes(self,*_): self.job('A importar os temas guardados no Aether…',lambda: f'{core.import_aether()} temas do Aether atualizados.')
        def save_dialog(self,*_):
            dialog=Gtk.Window(title='Guardar ambiente',transient_for=self.win,modal=True,default_width=360)
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12)
            for side in ['top','bottom','start','end']: getattr(box,'set_margin_'+side)(20)
            box.append(self.label('Nome do tema','section-title')); entry=Gtk.Entry(placeholder_text='O meu ambiente'); box.append(entry)
            def save(*_):
                name=entry.get_text().strip()
                if not name: return
                dialog.close(); self.job('A guardar o ambiente atual…',lambda:'Guardado: '+core.capture(name)['name'])
            box.append(self.button('Guardar',save,'suggested-action')); entry.connect('activate',save); dialog.set_child(box); dialog.present()
    return App().run([])

if __name__=='__main__': sys.exit(cli())
