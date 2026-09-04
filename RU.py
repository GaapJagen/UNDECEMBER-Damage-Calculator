import tkinter as tk
from tkinter import ttk
import math
import json
import shutil
from pathlib import Path
try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

APP_TITLE = 'UNDECEMBER Damage Calculator v0.14.40'
ASSET_DIR = Path(__file__).resolve().parent / 'assets'


def f(value):
    try:
        return float(str(value).replace(',', '.').strip() or 0)
    except ValueError:
        raise ValueError(f'Некорректное число: {value!r}')


def fmt(a, b):
    return f'{a:,.2f} – {b:,.2f}'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry('1420x900')
        self.minsize(1180, 760)
        self.vars = {}
        self.checks = {}
        self.multi_vars = {}
        self.multi_stacks = {}
        # Constellation calculation variables remain part of the calculator.
        for _k in ('constAtkInc','constAtkAmp','constSpellInc','constSpellAmp',
                   'constPhysInc','constPhysAmp','constFireInc','constFireAmp',
                   'constColdInc','constColdAmp','constPoisonInc','constPoisonAmp',
                   'constLightningInc','constLightningAmp','constElemInc','constElemAmp',
                   'constAreaInc','constAreaAmp','constProjInc','constProjAmp',
                   'constMeleeInc','constMeleeAmp','constStrikeInc','constStrikeAmp',
                   'constMaxDmg','constTripleDmg','constCritDmg',
                   'constGenericInc','constGenericAmp',
                   # Internal calculation coefficients. Hidden from the UI,
                   # but still required by reset() and calculate().
                   'physKMin','physKMax','elemKMin','elemKMax',
                   'areaKMin','areaKMax','projKMin','projKMax',
                   'meleeKMin','meleeKMax','strikeKMin','strikeKMax',
                   # Direct tooltip-input mode. These values are already the
                   # in-game skill tooltip and therefore bypass upstream
                   # character/skill/tag reconstruction.
                   'tooltipPMin','tooltipPMax','tooltipFMin','tooltipFMax',
                   'tooltipCMin','tooltipCMax','tooltipLMin','tooltipLMax',
                   'tooltipOMin','tooltipOMax','tooltipHMin','tooltipHMax'):
            self.var(_k, '0')
        self.editor_assets = {'background': None, 'node': None, 'branch': None}
        self.editor_asset_images = {}
        self._ensure_asset_dir()
        self._load_editor_assets()
        self._build()
        self.reset()

    def var(self, key, value='0'):
        v = tk.StringVar(value=str(value))
        self.vars[key] = v
        return v

    def entry(self, parent, key, value='0', width=10):
        e = ttk.Entry(parent, textvariable=self.var(key, value), width=width)
        e.grid_configure(padx=3, pady=2)
        return e

    def combo(self, parent, key, values, value=None, width=11):
        v = self.var(key, value if value is not None else values[0])
        c = ttk.Combobox(parent, textvariable=v, values=values, state='readonly', width=width)
        c.grid_configure(padx=3, pady=2)
        return c

    def checkbox(self, parent, key, text=''):
        v = tk.BooleanVar(value=False)
        self.checks[key] = v
        return ttk.Checkbutton(parent, text=text, variable=v)

    def multi_entry(self, parent, key, value='0', width=10):
        """Create one scalar stat with a '+' button for additional sources."""
        stack = ttk.Frame(parent)
        self.multi_vars[key] = []
        self.multi_stacks[key] = stack
        first = ttk.Frame(stack)
        first.pack(fill='x')
        v = self.var(key, value)
        self.multi_vars[key].append(v)
        ttk.Entry(first, textvariable=v, width=width).pack(side='left')
        ttk.Button(first, text='+', width=2, command=lambda k=key, w=width: self.add_source(k, w)).pack(side='left', padx=(2, 0))
        return stack

    def add_source(self, key, width=10):
        stack = self.multi_stacks[key]
        idx = len(self.multi_vars[key])
        row = ttk.Frame(stack)
        row.pack(fill='x', pady=(2, 0))
        v = tk.StringVar(value='0')
        self.multi_vars[key].append(v)
        ttk.Entry(row, textvariable=v, width=width).pack(side='left')
        ttk.Button(row, text='−', width=2, command=lambda k=key, i=idx, r=row: self.remove_source(k, i, r)).pack(side='left', padx=(2, 0))

    def remove_source(self, key, idx, row):
        row.destroy()
        self.multi_vars[key][idx].set('0')

    def multi_sum(self, key):
        return sum(f(v.get()) for v in self.multi_vars.get(key, []))

    def multi_amp_factor(self, key):
        factor = 1.0
        for v in self.multi_vars.get(key, []):
            factor *= (1 + f(v.get()) / 100.0)
        return factor

    def reset_multi(self, key, value):
        if key in self.multi_stacks:
            stack = self.multi_stacks[key]
            for child in list(stack.winfo_children())[1:]:
                child.destroy()
        self.multi_vars[key] = [self.vars[key]]
        self.vars[key].set(str(value))

    def _build(self):
        style = ttk.Style(self)
        try:
            style.theme_use('vista')
        except tk.TclError:
            pass

        root = ttk.Frame(self, padding=12)
        root.pack(fill='both', expand=True)

        ttk.Label(root, text=APP_TITLE, font=('Segoe UI', 16, 'bold')).pack(anchor='w')
        ttk.Label(root, text='Сначала строится tooltip, затем дополнительные уроны, крит, Double и Triple.', foreground='#555').pack(anchor='w', pady=(0, 8))

        notebook = ttk.Notebook(root)
        self.main_notebook = notebook
        notebook.pack(fill='both', expand=True)

        calc_tab = ttk.Frame(notebook)
        constellation_tab = ttk.Frame(notebook)
        editor_tab = ttk.Frame(notebook)
        self.editor_tab = editor_tab
        notebook.add(calc_tab, text='Калькулятор')
        notebook.add(constellation_tab, text='Созвездия')
        notebook.add(editor_tab, text='Редактор нодов')

        paned = ttk.Panedwindow(calc_tab, orient='horizontal')
        paned.pack(fill='both', expand=True)
        left = ttk.Frame(paned, padding=(0, 0, 8, 0))
        right = ttk.Frame(paned, padding=(8, 0, 0, 0))
        paned.add(left, weight=3)
        paned.add(right, weight=2)

        canvas = tk.Canvas(left, highlightthickness=0)
        scroll = ttk.Scrollbar(left, orient='vertical', command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=inner, anchor='nw')
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        self._character(inner)
        self._skill(inner)
        self._tags(inner)
        self._special(inner)
        self._post(inner)

        ttk.Label(right, text='РЕЗУЛЬТАТ / РАЗБОР', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        self.output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        self.output.pack(fill='both', expand=True, pady=(8, 8))
        buttons = ttk.Frame(right)
        buttons.pack(fill='x')
        ttk.Button(buttons, text='РАССЧИТАТЬ', command=self.calculate).pack(side='left', padx=(0, 6))
        ttk.Button(buttons, text='СБРОСИТЬ', command=self.reset).pack(side='left')

        self._constellation_runtime(constellation_tab)
        self._constellation_editor(editor_tab)

    def _ensure_asset_dir(self):
        ASSET_DIR.mkdir(parents=True, exist_ok=True)

    def _load_editor_assets(self):
        for key in ('background','node','branch'):
            path=ASSET_DIR / f'{key}.png'
            self.editor_assets[key]=str(path) if path.exists() else None

    def _editor_choose_asset(self, key):
        from tkinter import filedialog, messagebox
        path=filedialog.askopenfilename(title=f'Выбрать картинку: {key}',
            filetypes=[('Изображения','*.png *.gif *.ppm *.pgm'),('Все файлы','*.*')])
        if not path: return
        try:
            # Store a copy beside the application so the setting survives restart.
            dst=ASSET_DIR / f'{key}.png'
            if Image is not None:
                im=Image.open(path).convert('RGBA')
                im.save(dst, 'PNG')
            else:
                if Path(path).suffix.lower() != '.png':
                    raise ValueError('Для работы без Pillow нужна PNG-картинка.')
                shutil.copy2(path,dst)
            self.editor_assets[key]=str(dst)
            self._editor_refresh_asset_status()
            self._editor_draw()
            if hasattr(self,'editor_branch_bar'):
                self._editor_rebuild_branch_buttons()
        except Exception as e:
            messagebox.showerror('Картинка', f'Не удалось установить изображение:\n{e}')

    def _editor_reset_assets(self):
        from tkinter import messagebox
        if not messagebox.askyesno('Сбросить картинки','Удалить пользовательские картинки редактора?'):
            return
        for key in ('background','node','branch'):
            path=ASSET_DIR / f'{key}.png'
            try:
                if path.exists(): path.unlink()
            except OSError: pass
            self.editor_assets[key]=None
        self.editor_asset_images.clear()
        self._editor_refresh_asset_status()
        self._editor_rebuild_branch_buttons()
        self._editor_draw()

    def _editor_refresh_asset_status(self):
        active=[{'background':'фон','node':'ноды','branch':'ветки'}[k] for k,v in self.editor_assets.items() if v]
        text='Свои: '+', '.join(active)+'.' if active else 'Используются стандартные изображения.'
        if hasattr(self,'editor_asset_status'):
            self.editor_asset_status.config(text=text)

    def _editor_asset_image(self, key, size):
        path=self.editor_assets.get(key)
        if not path or not Path(path).exists(): return None
        cache_key=(key,size,path,Path(path).stat().st_mtime_ns)
        if cache_key in self.editor_asset_images: return self.editor_asset_images[cache_key]
        try:
            if Image is not None and ImageTk is not None:
                im=Image.open(path).convert('RGBA')
                im.thumbnail((size,size), Image.Resampling.LANCZOS)
                img=ImageTk.PhotoImage(im)
            else:
                img=tk.PhotoImage(file=path)
            self.editor_asset_images[cache_key]=img
            return img
        except Exception:
            return None

    # ---------------- WORKING CONSTELLATIONS ----------------
    def _constellation_runtime(self, p):
        """Playable Zodiac view. JSON supplies the graph and node effects;
        clicking a node toggles it on/off. A non-root node is available only
        when at least one linked predecessor is active."""
        outer=ttk.Frame(p,padding=8); outer.pack(fill='both',expand=True)
        top=ttk.Frame(outer); top.pack(fill='x')
        ttk.Label(top,text='Рабочие созвездия',font=('Segoe UI',14,'bold')).pack(side='left')
        ttk.Button(top,text='Загрузить JSON',command=self._runtime_load_json).pack(side='right')
        ttk.Button(top,text='Сбросить ноды',command=self._runtime_reset).pack(side='right',padx=4)
        self.runtime_status=ttk.Label(outer,text='Загрузи JSON с созвездиями.'); self.runtime_status.pack(anchor='w',pady=(4,6))
        self.runtime_const=tk.IntVar(value=1); self.runtime_branch=tk.IntVar(value=1)
        bar=ttk.Frame(outer); bar.pack(fill='x',pady=(0,5))
        self.runtime_const_buttons=[]
        for i in range(1,10):
            b=ttk.Radiobutton(bar,text=str(i),value=i,variable=self.runtime_const,command=self._runtime_const_changed,width=4)
            b.pack(side='left',padx=2); self.runtime_const_buttons.append(b)
        self.runtime_branch_bar=ttk.Frame(outer); self.runtime_branch_bar.pack(fill='x',pady=(0,5))
        pane=ttk.Panedwindow(outer,orient='horizontal'); pane.pack(fill='both',expand=True)
        left=ttk.Frame(pane); right=ttk.Frame(pane,padding=(10,0,0,0)); pane.add(left,weight=4); pane.add(right,weight=1)
        self.runtime_canvas=tk.Canvas(left,highlightthickness=0); self.runtime_canvas.pack(fill='both',expand=True)
        self.runtime_canvas.bind('<Configure>',lambda e:self._runtime_draw())
        self.runtime_canvas.bind('<Button-1>',self._runtime_click)
        ttk.Label(right,text='АКТИВНЫЕ БОНУСЫ',font=('Segoe UI',11,'bold')).pack(anchor='w')
        self.runtime_bonus=ttk.Label(right,text='Нет активных нодов.',justify='left',wraplength=300)
        self.runtime_bonus.pack(anchor='w',pady=(8,12))
        ttk.Label(right,text='Правило доступа',font=('Segoe UI',10,'bold')).pack(anchor='w')
        ttk.Label(right,text='Корневой нод можно взять сразу.\nОстальные доступны, если уже активирован хотя бы один нод, связанный с ним.',justify='left',wraplength=300).pack(anchor='w',pady=(4,0))
        self.runtime_nodes=self._make_editor_default_nodes()
        for _branches in self.runtime_nodes.values():
            for _nodes in _branches.values():
                self._editor_normalize_nodes(_nodes)
        self.runtime_active=set()
        self._runtime_rebuild_branches(); self._runtime_draw(); self._runtime_update_bonuses()

    def _runtime_load_json(self):
        from tkinter import filedialog,messagebox
        path=filedialog.askopenfilename(title='Загрузить созвездия',filetypes=[('JSON','*.json'),('Все файлы','*.*')])
        if not path:return
        try:
            with open(path,'r',encoding='utf-8') as fh: data=json.load(fh)
            consts=data.get('constellations',data)
            if not isinstance(consts,dict): raise ValueError('В JSON нет объекта constellations.')
            normalized={}
            for ck,branches in consts.items():
                if not isinstance(branches,dict): continue
                normalized[str(ck)]={}
                for bk,nodes in branches.items():
                    out=[]
                    for n in nodes or []:
                        if not isinstance(n,dict) or not n.get('id'): continue
                        q=dict(n); q.setdefault('x',.5); q.setdefault('y',.5); q.setdefault('name','Нод'); q.setdefault('effect','No parameter'); q.setdefault('value',0); q.setdefault('parent_id',None); q.setdefault('links',[]); q.setdefault('root', q.get('parent_id') is None)
                        out.append(q)
                    normalized[str(ck)][str(bk)]=out
            self.runtime_nodes=normalized
            self.runtime_active=set(); self.runtime_const.set(1)
            self._runtime_rebuild_branches(); self._runtime_draw(); self._runtime_update_bonuses()
            self.runtime_status.config(text=f'Загружено созвездий: {len(normalized)}.')
        except Exception as e: messagebox.showerror('Созвездия',f'Не удалось загрузить JSON:\n{e}')

    def _runtime_reset(self):
        self.runtime_active=set(); self._runtime_draw(); self._runtime_update_bonuses(); self.calculate()

    def _runtime_current_branches(self):
        return self.runtime_nodes.get(str(self.runtime_const.get()),{})

    def _runtime_current_nodes(self):
        b=self._runtime_current_branches(); key=str(self.runtime_branch.get())
        if key not in b:
            keys=sorted((int(k) for k in b),key=int)
            if not keys:return []
            self.runtime_branch.set(keys[0]); key=str(keys[0])
        return b.get(key,[])

    def _runtime_rebuild_branches(self):
        for w in self.runtime_branch_bar.winfo_children():w.destroy()
        branches=self._runtime_current_branches(); keys=sorted((int(k) for k in branches),key=int)
        if not keys:return
        if self.runtime_branch.get() not in keys:self.runtime_branch.set(keys[0])
        for k in keys:
            ttk.Radiobutton(self.runtime_branch_bar,text=f'Ветка {k}',value=k,variable=self.runtime_branch,command=self._runtime_branch_changed).pack(side='left',padx=3)

    def _runtime_const_changed(self):
        self.runtime_branch.set(1); self._runtime_rebuild_branches(); self._runtime_draw(); self._runtime_update_bonuses(); self.calculate()

    def _runtime_branch_changed(self):
        self._runtime_draw(); self._runtime_update_bonuses(); self.calculate()

    def _runtime_all_nodes(self):
        for branches in self.runtime_nodes.values():
            for nodes in branches.values():
                for n in nodes: yield n

    def _runtime_node_map(self): return {n.get('id'):n for n in self._runtime_all_nodes()}

    def _runtime_neighbors(self,node,nodes):
        # Accept either the current branch as a list or a node-id -> node mapping.
        if isinstance(nodes, dict):
            by_id = nodes
            iterable = nodes.values()
        else:
            iterable = nodes
            by_id = {n.get('id'): n for n in nodes if isinstance(n, dict) and n.get('id')}
        ids=set(node.get('links',[]) or [])
        if node.get('parent_id'): ids.add(node['parent_id'])
        # A link is undirected in the working constellation: either side can unlock the other.
        for other in iterable:
            if not isinstance(other, dict):
                continue
            if node.get('id') in (other.get('links',[]) or []) or other.get('parent_id')==node.get('id'):
                ids.add(other.get('id'))
        return [by_id[i] for i in ids if i in by_id]

    def _runtime_available(self,node,nodes):
        if bool(node.get('root', node.get('parent_id') is None)): return True
        return any(x.get('id') in self.runtime_active for x in self._runtime_neighbors(node,nodes))

    def _runtime_click(self,event):
        c=self.runtime_canvas; w=max(c.winfo_width(),1); h=max(c.winfo_height(),1)
        nodes=self._runtime_current_nodes(); hit=None
        for n in nodes:
            x=n.get('x',.5)*w; y=n.get('y',.5)*h
            if (event.x-x)**2+(event.y-y)**2 <= 22**2: hit=n; break
        if not hit:return
        nid=hit['id']; allmap=self._runtime_node_map()
        if nid in self.runtime_active:
            # Do not leave children active when their only prerequisite is removed.
            self.runtime_active.remove(nid)
            changed=True
            while changed:
                changed=False
                for aid in list(self.runtime_active):
                    an=allmap.get(aid)
                    if an and not self._runtime_available(an,allmap): self.runtime_active.remove(aid); changed=True
            msg=f"Выключен: {hit.get('name','Нод')}"
        elif self._runtime_available(hit,allmap):
            self.runtime_active.add(nid); msg=f"Активирован: {hit.get('name','Нод')}"
        else:
            msg='Нод недоступен: сначала активируй связанный предыдущий нод.'
        self.runtime_status.config(text=msg); self._runtime_draw(); self._runtime_update_bonuses(); self.calculate()

    def _runtime_draw(self):
        if not hasattr(self,'runtime_canvas'):return
        c=self.runtime_canvas;c.delete('all');w=max(c.winfo_width(),1);h=max(c.winfo_height(),1)
        # Reuse editor background and node artwork.
        bg=self._editor_asset_image('background',max(w,h))
        if bg:c.create_image(w/2,h/2,image=bg,anchor='center');c._runtime_bg=bg
        else:c.create_rectangle(0,0,w,h,fill='#06131b',outline='')
        nodes=self._runtime_current_nodes(); by={n.get('id'):n for n in nodes}; drawn=set()
        for n in nodes:
            targets=list(n.get('links',[]) or [])
            if n.get('parent_id'):targets.append(n['parent_id'])
            for tid in targets:
                o=by.get(tid)
                if not o:continue
                edge=tuple(sorted((n['id'],o['id'])))
                if edge in drawn:continue
                active=n['id'] in self.runtime_active and o['id'] in self.runtime_active
                c.create_line(n.get('x',.5)*w,n.get('y',.5)*h,o.get('x',.5)*w,o.get('y',.5)*h,fill='#9bd5df' if active else '#477887',width=3 if active else 2)
                drawn.add(edge)
        for n in nodes:
            x=n.get('x',.5)*w;y=n.get('y',.5)*h;nid=n['id'];active=nid in self.runtime_active;available=self._runtime_available(n,by)
            img=self._editor_asset_image('node',44 if active else 36)
            if img:c.create_image(x,y,image=img);c._runtime_node_img=img
            else:
                fill='#9feef8' if active else ('#315d69' if available else '#17282d'); outline='#eaffff' if active else '#477887'
                c.create_oval(x-15,y-15,x+15,y+15,fill=fill,outline=outline,width=2);c.create_text(x,y,text='✓' if active else '◆',fill='#08232b' if active else '#b7d1d6',font=('Segoe UI',10,'bold'))
            c.create_text(x+20,y-14,text=n.get('name','Нод'),anchor='w',fill='#e6f3f5' if available else '#71858a',font=('Segoe UI',9,'bold' if active else 'normal'))
        c.create_text(10,10,text=f'Созвездие {self.runtime_const.get()} — ветка {self.runtime_branch.get()}',anchor='nw',fill='#d7e7ea',font=('Segoe UI',11,'bold'))

    def _runtime_update_bonuses(self):
        totals={}
        for n in self._runtime_all_nodes():
            if n.get('id') in self.runtime_active:
                eff=n.get('effect','No parameter'); val=float(n.get('value',0) or 0); totals[eff]=totals.get(eff,0)+val
        self.runtime_bonus.config(text='\n'.join(f'{k}: +{v:g}%' for k,v in totals.items()) if totals else 'Нет активных нодов.')
        self._runtime_apply_to_vars()

    def _runtime_apply_to_vars(self):
        mapping={'Attack Damage Increase':'constAtkInc','Attack Damage Amplification':'constAtkAmp','Spell Damage Increase':'constSpellInc','Spell Damage Amplification':'constSpellAmp','Physical Damage Increase':'constPhysInc','Physical Damage Amplification':'constPhysAmp','Fire Damage Increase':'constFireInc','Fire Damage Amplification':'constFireAmp','Cold Damage Increase':'constColdInc','Cold Damage Amplification':'constColdAmp','Lightning Damage Increase':'constLightningInc','Lightning Damage Amplification':'constLightningAmp','Poison Damage Increase':'constPoisonInc','Poison Damage Amplification':'constPoisonAmp','Elemental Damage Increase':'constElemInc','Elemental Damage Amplification':'constElemAmp','Area Damage Increase':'constAreaInc','Area Damage Amplification':'constAreaAmp','Strike Damage Increase':'constStrikeInc','Strike Damage Amplification':'constStrikeAmp','Projectile Damage Increase':'constProjInc','Projectile Damage Amplification':'constProjAmp','Melee Damage Increase':'constMeleeInc','Melee Damage Amplification':'constMeleeAmp','Double Maximum Damage Increase':'constMaxDmg','Triple Maximum Damage Increase':'constTripleDmg','Critical Damage Increase':'constCritDmg','Generic Damage Increase':'constGenericInc','Generic Damage Amplification':'constGenericAmp'}
        vals={k:0.0 for k in mapping.values()}
        amp_keys={
            'constAtkAmp','constSpellAmp','constPhysAmp','constFireAmp','constColdAmp',
            'constPoisonAmp','constLightningAmp','constElemAmp','constAreaAmp',
            'constProjAmp','constMeleeAmp','constStrikeAmp','constGenericAmp'
        }
        amp_products={k:1.0 for k in amp_keys}
        for n in self._runtime_all_nodes():
            if n.get('id') not in self.runtime_active:
                continue
            eff=n.get('effect','No parameter')
            v=float(n.get('value',0) or 0)
            if eff=='Maximum Damage Increase':
                vals['constMaxDmg']+=v
                vals['constTripleDmg']+=2*v
            elif eff in mapping:
                target=mapping[eff]
                if target in amp_keys:
                    amp_products[target] *= (1.0 + v/100.0)
                else:
                    vals[target] += v
        # A single Elemental Damage modifier applies independently to all four
        # elemental types. Increase remains additive; Amplification remains a
        # product of independent multipliers.
        elem_inc=vals['constElemInc']
        elem_amp=amp_products['constElemAmp']
        for k in ('constFireInc','constColdInc','constLightningInc','constPoisonInc'):
            vals[k] += elem_inc
        for k in ('constFireAmp','constColdAmp','constLightningAmp','constPoisonAmp'):
            amp_products[k] *= elem_amp
        for k,v in amp_products.items():
            vals[k]=(v-1.0)*100.0
        for k,v in vals.items():
            self.vars[k].set(str(v))
        # These vars are read directly by calculate(); changing a constellation
        # node therefore immediately changes the next calculation.

    def _constellation_editor(self, p):
        """Interactive layout editor for the Zodiac node map.

        The editor deliberately stores only geometry/branch metadata.  It does
        not alter the damage formulas.  The exported JSON is the handoff file
        that can be uploaded back into ChatGPT after the user positions nodes.
        """
        outer = ttk.Frame(p, padding=8)
        outer.pack(fill='both', expand=True)

        top = ttk.Frame(outer)
        top.pack(fill='x', pady=(0, 6))
        ttk.Label(top, text='Редактор расположения нодов', font=('Segoe UI', 14, 'bold')).pack(side='left')
        ttk.Label(top, text='Перетаскивай ноды мышью. После настройки нажми «Экспорт JSON» и пришли файл.', foreground='#666').pack(side='left', padx=14)

        controls = ttk.Frame(outer)
        controls.pack(fill='x', pady=(0, 6))
        ttk.Label(controls, text='Созвездие:').pack(side='left')
        self.editor_constellation = tk.IntVar(value=1)
        for n in range(1, 10):
            ttk.Radiobutton(controls, text=chr(0x2160+n-1), value=n,
                            variable=self.editor_constellation,
                            command=self._editor_selection_changed).pack(side='left', padx=2)
        ttk.Label(controls, text='   Ветки:').pack(side='left', padx=(10, 0))
        self.editor_branch = tk.IntVar(value=1)
        self.editor_branch_buttons=[]
        self.editor_branch_bar = ttk.Frame(controls)
        self.editor_branch_bar.pack(side='left', padx=(2, 0))
        ttk.Button(controls, text='+ Ветка', command=self._editor_add_branch).pack(side='left', padx=(8,3))
        ttk.Button(controls, text='− Ветка', command=self._editor_delete_branch).pack(side='left', padx=3)
        ttk.Button(controls, text='+ Нод', command=self._editor_add_node).pack(side='left', padx=(10,3))
        ttk.Button(controls, text='− Нод', command=self._editor_delete_node).pack(side='left', padx=3)
        ttk.Button(controls, text='↔ Связать', command=self._editor_start_link).pack(side='left', padx=(10,3))
        ttk.Button(controls, text='− Связь', command=self._editor_unlink_selected).pack(side='left', padx=3)
        ttk.Button(controls, text='Сохранить JSON', command=self._editor_save_json).pack(side='right', padx=3)
        ttk.Button(controls, text='Загрузить JSON', command=self._editor_load_json).pack(side='right', padx=3)
        ttk.Button(controls, text='Экспорт JSON', command=self._editor_export_json).pack(side='right', padx=3)

        assets=ttk.LabelFrame(outer,text='Картинки редактора',padding=6)
        assets.pack(fill='x', pady=(0,6))
        ttk.Button(assets,text='Фон…',command=lambda:self._editor_choose_asset('background')).pack(side='left',padx=2)
        ttk.Button(assets,text='Иконка нода…',command=lambda:self._editor_choose_asset('node')).pack(side='left',padx=2)
        ttk.Button(assets,text='Иконка ветки…',command=lambda:self._editor_choose_asset('branch')).pack(side='left',padx=2)
        ttk.Button(assets,text='Сбросить картинки',command=self._editor_reset_assets).pack(side='left',padx=(10,2))
        self.editor_asset_status=ttk.Label(assets,text='Используются стандартные изображения.',foreground='#666')
        self.editor_asset_status.pack(side='left',padx=10)

        body=ttk.Frame(outer)
        body.pack(fill='both', expand=True)

        self.editor_canvas=tk.Canvas(body, bg='#06131b', highlightthickness=0, cursor='crosshair')
        self.editor_canvas.pack(side='left', fill='both', expand=True)
        self.editor_canvas.bind('<Configure>', lambda e:self._editor_draw())
        self.editor_canvas.bind('<Button-1>', self._editor_mouse_down)
        self.editor_canvas.bind('<B1-Motion>', self._editor_mouse_drag)
        self.editor_canvas.bind('<ButtonRelease-1>', self._editor_mouse_up)

        side=ttk.Frame(body, width=260, padding=(10,0,0,0))
        side.pack(side='right', fill='y')
        side.pack_propagate(False)

        lf=ttk.LabelFrame(side,text='Выбранный нод',padding=8)
        lf.pack(fill='x',pady=(0,8))
        self.editor_node_label=ttk.Label(lf,text='Нод не выбран',font=('Segoe UI',10,'bold'),wraplength=230)
        self.editor_node_label.pack(anchor='w')
        self.editor_node_coords=ttk.Label(lf,text='X: —   Y: —',foreground='#666')
        self.editor_node_coords.pack(anchor='w',pady=(5,0))

        ttk.Label(lf,text='Название нода (автоматически):').pack(anchor='w',pady=(8,2))
        self.editor_node_name_var=tk.StringVar(value='')
        self.editor_node_name_entry=ttk.Entry(lf,textvariable=self.editor_node_name_var,state='readonly')
        self.editor_node_name_entry.pack(fill='x')

        ttk.Label(lf,text='Параметр нода:').pack(anchor='w',pady=(8,2))
        self.editor_effect_var=tk.StringVar(value='No parameter')
        effect_values=[
            'Attack Damage Increase','Attack Damage Amplification',
            'Spell Damage Increase','Spell Damage Amplification',
            'Physical Damage Increase','Physical Damage Amplification',
            'Elemental Damage Increase','Elemental Damage Amplification',
            'Fire Damage Increase','Fire Damage Amplification',
            'Cold Damage Increase','Cold Damage Amplification',
            'Lightning Damage Increase','Lightning Damage Amplification',
            'Poison Damage Increase','Poison Damage Amplification',
            'Projectile Damage Increase','Projectile Damage Amplification',
            'Melee Damage Increase','Melee Damage Amplification',
            'Area Damage Increase','Area Damage Amplification',
            'Strike Damage Increase','Strike Damage Amplification',
            'Double Maximum Damage Increase','Triple Maximum Damage Increase',
            'Critical Damage Increase','Generic Damage Increase','Generic Damage Amplification',
            'No parameter'
        ]
        self.editor_effect_combo=ttk.Combobox(lf,textvariable=self.editor_effect_var,values=effect_values,state='readonly')
        self.editor_effect_combo.pack(fill='x')

        ttk.Label(lf,text='Значение %:').pack(anchor='w',pady=(8,2))
        self.editor_effect_value_var=tk.StringVar(value='0')
        self.editor_effect_value_entry=ttk.Entry(lf,textvariable=self.editor_effect_value_var)
        self.editor_effect_value_entry.pack(fill='x')

        # Description is a live preview: changing either the parameter or
        # the value updates the text immediately, without pressing Apply.
        self.editor_effect_var.trace_add('write', self._editor_description_preview)
        self.editor_effect_value_var.trace_add('write', self._editor_description_preview)

        ttk.Label(lf,text='Описание нода (автоматически):').pack(fill='x',pady=(8,2))
        self.editor_description_var=tk.StringVar(value='')
        self.editor_description_label=ttk.Label(lf,textvariable=self.editor_description_var,wraplength=230,justify='left',foreground='#9fc7cf')
        self.editor_description_label.pack(fill='x')

        self.editor_root_var=tk.BooleanVar(value=False)
        ttk.Checkbutton(lf,text='Корневой нод (начальный)',variable=self.editor_root_var).pack(anchor='w',pady=(8,0))
        ttk.Label(lf,text='Корневой нод доступен сразу при входе в ветку. В одной ветке может быть несколько корневых нодов.',foreground='#666',wraplength=230,justify='left').pack(anchor='w',pady=(2,0))

        ttk.Button(lf,text='Применить к ноду',command=self._editor_apply_node_fields).pack(fill='x',pady=(8,0))

        self.editor_node_hint=ttk.Label(lf,text='ЛКМ по ноду → справа выбери параметр и значение. Эти данные сохраняются в JSON.',foreground='#666',wraplength=230,justify='left')
        self.editor_node_hint.pack(anchor='w',pady=(8,0))

        lf2=ttk.LabelFrame(side,text='Справка',padding=8)
        lf2.pack(fill='x',pady=(0,8))
        ttk.Label(lf2,text=(
            'Позиции сохраняются как относительные координаты 0..1 внутри карты.\n\n'
            '• Созвездие — I–IX\n'
            '• У каждого созвездия может быть любое число веток\n'
            '• Ноды можно двигать независимо\n'
            '• «Добавить нод» из выбранного нода создаёт дочерний нод и связь\n'
            '• Можно сделать несколько нодов корневыми — каждый будет доступен сразу\n'
            '• JSON можно прислать мне — я использую его как точную схему'
        ),justify='left',wraplength=235).pack(anchor='w')

        self.editor_status=ttk.Label(side,text='Готово.',foreground='#666',wraplength=235,justify='left')
        self.editor_status.pack(anchor='w',pady=(4,0))

        self.editor_nodes=self._make_editor_default_nodes()
        self.editor_selected_id=None
        self.editor_drag_id=None
        self.editor_drag_offset=(0,0)
        self.editor_link_mode=False
        self.editor_link_source_id=None
        self._editor_rebuild_branch_buttons()
        self._editor_refresh_asset_status()
        self._editor_draw()
        # Editor hotkeys: E = add node, R = start linking.  They are bound
        # globally so they continue to work after clicking buttons, while
        # _editor_hotkey limits them to the editor tab and ignores text fields.
        if not getattr(self, '_editor_hotkeys_bound', False):
            self.bind_all('<KeyPress>', self._editor_hotkey, add='+')
            self._editor_hotkeys_bound = True

    def _make_editor_default_nodes(self):
        """Built-in base constellation layout supplied by the user."""
        return json.loads(r'''{
  "1": {
    "1": [
      {
        "id": "1-1-1",
        "x": 0.3012871287128713,
        "y": 0.3995370370370371,
        "name": "Урон при атаке: +5%",
        "effect": "Attack Damage Increase",
        "type": "node",
        "parent_id": null,
        "value": 5.0,
        "root": true,
        "links": [
          "1-1-2",
          "1-1-3"
        ],
        "description": "Урон при атаке: +5%"
      },
      {
        "id": "1-1-2",
        "x": 0.3993069306930693,
        "y": 0.20532407407407405,
        "name": "",
        "effect": "",
        "type": "node",
        "parent_id": "1-1-1",
        "root": false,
        "links": [
          "1-1-1",
          "1-1-4"
        ],
        "value": 0,
        "description": ""
      },
      {
        "id": "1-1-3",
        "x": 0.3994306930693069,
        "y": 0.6103240740740742,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-1-1",
        "root": false,
        "links": [
          "1-1-1",
          "1-1-6"
        ],
        "description": ""
      },
      {
        "id": "1-1-4",
        "x": 0.4999257425742574,
        "y": 0.24828703703703703,
        "name": "Урон при атаке: +10%",
        "effect": "Attack Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": "1-1-2",
        "root": false,
        "links": [
          "1-1-2",
          "1-1-5"
        ],
        "description": "Урон при атаке: +10%"
      },
      {
        "id": "1-1-5",
        "x": 0.6011633663366337,
        "y": 0.2021296296296296,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-1-4",
        "root": false,
        "links": [
          "1-1-4",
          "1-1-8"
        ],
        "description": ""
      },
      {
        "id": "1-1-6",
        "x": 0.5006683168316831,
        "y": 0.5514351851851852,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-1-3",
        "root": false,
        "links": [
          "1-1-3",
          "1-1-7"
        ],
        "description": ""
      },
      {
        "id": "1-1-7",
        "x": 0.6019059405940593,
        "y": 0.6024999999999999,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-1-6",
        "root": false,
        "links": [
          "1-1-6",
          "1-1-8"
        ],
        "description": ""
      },
      {
        "id": "1-1-8",
        "x": 0.7011633663366336,
        "y": 0.4013425925925926,
        "name": "Повышает УРН при атаке: +3%",
        "effect": "Attack Damage Amplification",
        "value": 3.0,
        "type": "node",
        "parent_id": "1-1-5",
        "root": false,
        "links": [
          "1-1-5",
          "1-1-7"
        ],
        "description": "Повышает УРН при атаке: +3%"
      }
    ],
    "3": [
      {
        "id": "1-3-1",
        "x": 0.39851485148514854,
        "y": 0.40046296296296297,
        "name": "Урон при использовании заклинания: +5%",
        "effect": "Spell Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": null,
        "root": true,
        "links": [
          "1-3-2",
          "1-3-4"
        ],
        "description": "Урон при использовании заклинания: +5%"
      },
      {
        "id": "1-3-2",
        "x": 0.34690594059405944,
        "y": 0.5996759259259259,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-3-1",
        "root": false,
        "links": [
          "1-3-1",
          "1-3-3"
        ],
        "description": ""
      },
      {
        "id": "1-3-3",
        "x": 0.5508663366336634,
        "y": 0.49796296296296283,
        "name": "Урон при использовании заклинания: +10%",
        "effect": "Spell Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": "1-3-2",
        "root": false,
        "links": [
          "1-3-2",
          "1-3-7"
        ],
        "description": "Урон при использовании заклинания: +10%"
      },
      {
        "id": "1-3-4",
        "x": 0.44653465346534654,
        "y": 0.46078703703703705,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-3-1",
        "root": false,
        "links": [
          "1-3-1",
          "1-3-5"
        ],
        "description": ""
      },
      {
        "id": "1-3-5",
        "x": 0.5007425742574257,
        "y": 0.3509722222222222,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-3-4",
        "root": false,
        "links": [
          "1-3-4",
          "1-3-6"
        ],
        "description": ""
      },
      {
        "id": "1-3-6",
        "x": 0.5834158415841583,
        "y": 0.3256481481481481,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-3-5",
        "root": false,
        "links": [
          "1-3-5",
          "1-3-8"
        ],
        "description": ""
      },
      {
        "id": "1-3-7",
        "x": 0.6007425742574257,
        "y": 0.5987962962962962,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-3-3",
        "root": false,
        "links": [
          "1-3-3",
          "1-3-8"
        ],
        "description": ""
      },
      {
        "id": "1-3-8",
        "x": 0.6388613861386138,
        "y": 0.4275494135032786,
        "name": "Повышает УРН при использовании заклинания: +3%",
        "effect": "Spell Damage Amplification",
        "value": 3.0,
        "type": "node",
        "parent_id": "1-3-7",
        "root": false,
        "links": [
          "1-3-7",
          "1-3-6"
        ],
        "description": "Повышает УРН при использовании заклинания: +3%"
      }
    ],
    "4": [
      {
        "id": "1-4-1",
        "x": 0.39913366336633666,
        "y": 0.5011574074074074,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": null,
        "root": true,
        "links": [
          "1-4-2",
          "1-4-3"
        ],
        "description": ""
      },
      {
        "id": "1-4-2",
        "x": 0.3530940594059407,
        "y": 0.355462962962963,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-4-1",
        "root": false,
        "links": [
          "1-4-1",
          "1-4-5"
        ],
        "description": ""
      },
      {
        "id": "1-4-3",
        "x": 0.35990099009901,
        "y": 0.6436574074074074,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-4-1",
        "root": false,
        "links": [
          "1-4-1",
          "1-4-4"
        ],
        "description": ""
      },
      {
        "id": "1-4-4",
        "x": 0.5013613861386139,
        "y": 0.5986574074074075,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-4-3",
        "root": false,
        "links": [
          "1-4-3",
          "1-4-7"
        ],
        "description": ""
      },
      {
        "id": "1-4-5",
        "x": 0.4580445544554456,
        "y": 0.43083333333333335,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-4-2",
        "root": false,
        "links": [
          "1-4-2",
          "1-4-6"
        ],
        "description": ""
      },
      {
        "id": "1-4-6",
        "x": 0.5592821782178219,
        "y": 0.38930555555555557,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-4-5",
        "root": false,
        "links": [
          "1-4-5",
          "1-4-8"
        ],
        "description": ""
      },
      {
        "id": "1-4-7",
        "x": 0.6007425742574258,
        "y": 0.6346759259259259,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-4-4",
        "root": false,
        "links": [
          "1-4-4",
          "1-4-8"
        ],
        "description": ""
      },
      {
        "id": "1-4-8",
        "x": 0.6574257425742575,
        "y": 0.49129629629629634,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "1-4-7",
        "root": false,
        "links": [
          "1-4-7",
          "1-4-6"
        ],
        "description": ""
      }
    ]
  },
  "2": {
    "1": [
      {
        "id": "2-1-1",
        "x": 0.2998762376237623,
        "y": 0.4020833333333333,
        "name": "",
        "effect": "",
        "type": "node",
        "parent_id": null,
        "root": true,
        "links": [
          "2-1-2",
          "2-1-5"
        ],
        "value": 0,
        "description": ""
      },
      {
        "id": "2-1-2",
        "x": 0.2570049504950495,
        "y": 0.3,
        "name": "",
        "effect": "",
        "type": "node",
        "parent_id": "2-1-1",
        "root": false,
        "links": [
          "2-1-1",
          "2-1-3"
        ],
        "value": 0,
        "description": ""
      },
      {
        "id": "2-1-3",
        "x": 0.41022277227722775,
        "y": 0.23880206890181951,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-1-2",
        "root": false,
        "links": [
          "2-1-2",
          "2-1-4",
          "2-1-7"
        ],
        "description": ""
      },
      {
        "id": "2-1-4",
        "x": 0.5461138613861386,
        "y": 0.29912037037037037,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-1-3",
        "root": false,
        "links": [
          "2-1-3",
          "2-1-9"
        ],
        "description": ""
      },
      {
        "id": "2-1-5",
        "x": 0.3757425742574257,
        "y": 0.3999074074074074,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-1-1",
        "root": false,
        "links": [
          "2-1-1",
          "2-1-6"
        ],
        "description": ""
      },
      {
        "id": "2-1-6",
        "x": 0.40396039603960393,
        "y": 0.5366203703703704,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-1-5",
        "root": false,
        "links": [
          "2-1-5",
          "2-1-7",
          "2-1-8"
        ],
        "description": ""
      },
      {
        "id": "2-1-7",
        "x": 0.4495049504950495,
        "y": 0.3467597210677011,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-1-6",
        "root": false,
        "links": [
          "2-1-6",
          "2-1-3"
        ],
        "description": ""
      },
      {
        "id": "2-1-8",
        "x": 0.5262376237623763,
        "y": 0.5367592592592593,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-1-6",
        "root": false,
        "links": [
          "2-1-6",
          "2-1-9"
        ],
        "description": ""
      },
      {
        "id": "2-1-9",
        "x": 0.5191831683168316,
        "y": 0.4084259259259259,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-1-8",
        "root": false,
        "links": [
          "2-1-8",
          "2-1-4"
        ],
        "description": ""
      }
    ],
    "2": [
      {
        "id": "2-2-1",
        "x": 0.39913366336633666,
        "y": 0.5,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": null,
        "root": true,
        "links": [
          "2-2-2",
          "2-2-3"
        ],
        "description": ""
      },
      {
        "id": "2-2-2",
        "x": 0.35804455445544564,
        "y": 0.6043055555555554,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-2-1",
        "root": false,
        "links": [
          "2-2-1",
          "2-2-6"
        ],
        "description": ""
      },
      {
        "id": "2-2-3",
        "x": 0.3097772277227724,
        "y": 0.4399537037037036,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-2-1",
        "root": false,
        "links": [
          "2-2-1",
          "2-2-4"
        ],
        "description": ""
      },
      {
        "id": "2-2-4",
        "x": 0.46856435643564365,
        "y": 0.36717592592592585,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-2-3",
        "root": false,
        "links": [
          "2-2-3",
          "2-2-5",
          "2-2-7"
        ],
        "description": ""
      },
      {
        "id": "2-2-5",
        "x": 0.6254950495049505,
        "y": 0.2897685185185185,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-2-4",
        "root": false,
        "links": [
          "2-2-4",
          "2-2-9"
        ],
        "description": ""
      },
      {
        "id": "2-2-6",
        "x": 0.511881188118812,
        "y": 0.6588425925925925,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-2-2",
        "root": false,
        "links": [
          "2-2-2",
          "2-2-7",
          "2-2-8"
        ],
        "description": ""
      },
      {
        "id": "2-2-7",
        "x": 0.4565594059405942,
        "y": 0.5411106493026692,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-2-6",
        "root": false,
        "links": [
          "2-2-6",
          "2-2-4"
        ],
        "description": ""
      },
      {
        "id": "2-2-8",
        "x": 0.5797029702970298,
        "y": 0.5987962962962962,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-2-6",
        "root": false,
        "links": [
          "2-2-6",
          "2-2-9"
        ],
        "description": ""
      },
      {
        "id": "2-2-9",
        "x": 0.6116336633663367,
        "y": 0.4368981481481479,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-2-8",
        "root": false,
        "links": [
          "2-2-8",
          "2-2-5"
        ],
        "description": ""
      }
    ],
    "3": [
      {
        "id": "2-3-1",
        "x": 0.20111386138613863,
        "y": 0.5023148148148148,
        "name": "Стихийный урон: +10%",
        "effect": "Elemental Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": null,
        "root": true,
        "links": [
          "2-3-2",
          "2-3-6",
          "2-3-10",
          "2-3-14"
        ],
        "description": "Стихийный урон: +10%"
      },
      {
        "id": "2-3-2",
        "x": 0.2621287128712871,
        "y": 0.27560185185185176,
        "name": "Огненный урон: +5%",
        "effect": "Fire Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "2-3-1",
        "root": false,
        "links": [
          "2-3-1",
          "2-3-3"
        ],
        "description": "Огненный урон: +5%"
      },
      {
        "id": "2-3-3",
        "x": 0.3850247524752475,
        "y": 0.3093055555555555,
        "name": "Огненный урон: +15%",
        "effect": "Fire Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "2-3-2",
        "root": false,
        "links": [
          "2-3-2",
          "2-3-4"
        ],
        "description": "Огненный урон: +15%"
      },
      {
        "id": "2-3-4",
        "x": 0.513490099009901,
        "y": 0.28861111111111104,
        "name": "Огненный урон: +5%",
        "effect": "Fire Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "2-3-3",
        "root": false,
        "links": [
          "2-3-3",
          "2-3-5"
        ],
        "description": "Огненный урон: +5%"
      },
      {
        "id": "2-3-5",
        "x": 0.629579207920792,
        "y": 0.30611111111111106,
        "name": "Огненный урон: +3%(усиление)",
        "effect": "Fire Damage Amplification",
        "value": 3.0,
        "type": "node",
        "parent_id": "2-3-4",
        "root": false,
        "links": [
          "2-3-4"
        ],
        "description": "Огненный урон: +3%(усиление)"
      },
      {
        "id": "2-3-6",
        "x": 0.29925742574257425,
        "y": 0.40060185185185176,
        "name": "Урон холодом: +5%",
        "effect": "Cold Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "2-3-1",
        "root": false,
        "links": [
          "2-3-1",
          "2-3-7"
        ],
        "description": "Урон холодом: +5%"
      },
      {
        "id": "2-3-7",
        "x": 0.4221534653465347,
        "y": 0.4308333333333333,
        "name": "Урон холодом: +15%",
        "effect": "Cold Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "2-3-6",
        "root": false,
        "links": [
          "2-3-6",
          "2-3-8"
        ],
        "description": "Урон холодом: +15%"
      },
      {
        "id": "2-3-8",
        "x": 0.55,
        "y": 0.39046296296296285,
        "name": "Урон холодом: +5%",
        "effect": "Cold Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "2-3-7",
        "root": false,
        "links": [
          "2-3-7",
          "2-3-9"
        ],
        "description": "Урон холодом: +5%"
      },
      {
        "id": "2-3-9",
        "x": 0.6611386138613862,
        "y": 0.42185185185185176,
        "name": "Урон холодом: +3%(усиление)",
        "effect": "Cold Damage Amplification",
        "value": 3.0,
        "type": "node",
        "parent_id": "2-3-8",
        "root": false,
        "links": [
          "2-3-8"
        ],
        "description": "Урон холодом: +3%(усиление)"
      },
      {
        "id": "2-3-10",
        "x": 0.29987623762376237,
        "y": 0.5360185185185184,
        "name": "Урон молнией: +5%",
        "effect": "Lightning Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "2-3-1",
        "root": false,
        "links": [
          "2-3-1",
          "2-3-11"
        ],
        "description": "Урон молнией: +5%"
      },
      {
        "id": "2-3-11",
        "x": 0.3887376237623762,
        "y": 0.5593055555555554,
        "name": "Урон молнией: +15%",
        "effect": "Lightning Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "2-3-10",
        "root": false,
        "links": [
          "2-3-10",
          "2-3-12"
        ],
        "description": "Урон молнией: +15%"
      },
      {
        "id": "2-3-12",
        "x": 0.49368811881188107,
        "y": 0.5467129629629627,
        "name": "Урон молнией: +5%",
        "effect": "Lightning Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "2-3-11",
        "root": false,
        "links": [
          "2-3-11",
          "2-3-13"
        ],
        "description": "Урон молнией: +5%"
      },
      {
        "id": "2-3-13",
        "x": 0.5998762376237623,
        "y": 0.5364351851851848,
        "name": "Урон молнией: +3%(усиление)",
        "effect": "Lightning Damage Amplification",
        "value": 3.0,
        "type": "node",
        "parent_id": "2-3-12",
        "root": false,
        "links": [
          "2-3-12"
        ],
        "description": "Урон молнией: +3%(усиление)"
      },
      {
        "id": "2-3-14",
        "x": 0.2974009900990099,
        "y": 0.6714351851851851,
        "name": "Урон ядом: +5%",
        "effect": "Poison Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "2-3-1",
        "root": false,
        "links": [
          "2-3-1",
          "2-3-15"
        ],
        "description": "Урон ядом: +5%"
      },
      {
        "id": "2-3-15",
        "x": 0.4388613861386138,
        "y": 0.6565277777777777,
        "name": "Урон ядом: +15%",
        "effect": "Poison Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "2-3-14",
        "root": false,
        "links": [
          "2-3-14",
          "2-3-16"
        ],
        "description": "Урон ядом: +15%"
      },
      {
        "id": "2-3-16",
        "x": 0.550618811881188,
        "y": 0.6728703703703702,
        "name": "Урон ядом: +5%",
        "effect": "Poison Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "2-3-15",
        "root": false,
        "links": [
          "2-3-15",
          "2-3-17"
        ],
        "description": "Урон ядом: +5%"
      },
      {
        "id": "2-3-17",
        "x": 0.6549504950495049,
        "y": 0.6533333333333331,
        "name": "Урон ядом: +3%(усиление)",
        "effect": "Poison Damage Amplification",
        "value": 3.0,
        "type": "node",
        "parent_id": "2-3-16",
        "root": false,
        "links": [
          "2-3-16"
        ],
        "description": "Урон ядом: +3%(усиление)"
      }
    ],
    "4": [
      {
        "id": "2-4-1",
        "x": 0.3001237623762376,
        "y": 0.6018518518518519,
        "name": "Физический урон: +10%",
        "effect": "Physical Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": null,
        "root": true,
        "links": [
          "2-4-2",
          "2-4-7"
        ],
        "description": "Физический урон: +10%"
      },
      {
        "id": "2-4-2",
        "x": 0.3685643564356435,
        "y": 0.43069444444444444,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-4-1",
        "root": false,
        "links": [
          "2-4-1",
          "2-4-3"
        ],
        "description": ""
      },
      {
        "id": "2-4-3",
        "x": 0.4580445544554455,
        "y": 0.36717592592592596,
        "name": "Физический урон: +15%",
        "effect": "Physical Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "2-4-2",
        "root": false,
        "links": [
          "2-4-2",
          "2-4-4",
          "2-4-6"
        ],
        "description": "Физический урон: +15%"
      },
      {
        "id": "2-4-4",
        "x": 0.5530940594059406,
        "y": 0.40666666666666673,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-4-3",
        "root": false,
        "links": [
          "2-4-3",
          "2-4-5"
        ],
        "description": ""
      },
      {
        "id": "2-4-5",
        "x": 0.635148514851485,
        "y": 0.3906018518518519,
        "name": "Физический урон: +3%(усиление)",
        "effect": "Physical Damage Amplification",
        "value": 3.0,
        "type": "node",
        "parent_id": "2-4-4",
        "root": false,
        "links": [
          "2-4-4",
          "2-4-9"
        ],
        "description": "Физический урон: +3%(усиление)"
      },
      {
        "id": "2-4-6",
        "x": 0.48564356435643563,
        "y": 0.5053204950586497,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-4-3",
        "root": false,
        "links": [
          "2-4-3",
          "2-4-8"
        ],
        "description": ""
      },
      {
        "id": "2-4-7",
        "x": 0.4217821782178217,
        "y": 0.6563888888888889,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-4-1",
        "root": false,
        "links": [
          "2-4-1",
          "2-4-8"
        ],
        "description": ""
      },
      {
        "id": "2-4-8",
        "x": 0.5409653465346533,
        "y": 0.6310648148148148,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-4-7",
        "root": false,
        "links": [
          "2-4-7",
          "2-4-9",
          "2-4-6"
        ],
        "description": ""
      },
      {
        "id": "2-4-9",
        "x": 0.6063118811881186,
        "y": 0.5409259259259258,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "2-4-8",
        "root": false,
        "links": [
          "2-4-8",
          "2-4-5"
        ],
        "description": ""
      }
    ]
  },
  "3": {
    "1": [
      {
        "id": "3-1-1",
        "x": 0.29834158415841583,
        "y": 0.7041147132169576,
        "name": "",
        "effect": "",
        "type": "node",
        "parent_id": null,
        "root": true,
        "links": [
          "3-1-2"
        ],
        "value": 0,
        "description": ""
      },
      {
        "id": "3-1-2",
        "x": 0.343960396039604,
        "y": 0.5543142144638404,
        "name": "",
        "effect": "",
        "type": "node",
        "parent_id": "3-1-1",
        "root": false,
        "links": [
          "3-1-1",
          "3-1-3"
        ],
        "value": 0,
        "description": ""
      },
      {
        "id": "3-1-3",
        "x": 0.3981683168316832,
        "y": 0.6929177057356609,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-1-2",
        "links": [
          "3-1-2",
          "3-1-4"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-1-4",
        "x": 0.43504950495049505,
        "y": 0.6020947630922693,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-1-3",
        "links": [
          "3-1-3",
          "3-1-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-1-5",
        "x": 0.45769801980198027,
        "y": 0.49755610972568576,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-1-4",
        "links": [
          "3-1-4",
          "3-1-6",
          "3-1-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-1-6",
        "x": 0.49581683168316837,
        "y": 0.3630922693266832,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-1-5",
        "links": [
          "3-1-5",
          "3-1-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-1-7",
        "x": 0.5348019801980198,
        "y": 0.5451371571072319,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-1-5",
        "links": [
          "3-1-5",
          "3-1-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-1-8",
        "x": 0.5642574257425742,
        "y": 0.6687780548628428,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-1-7",
        "links": [
          "3-1-7",
          "3-1-9"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-1-9",
        "x": 0.6110396039603959,
        "y": 0.5654862842892766,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-1-8",
        "links": [
          "3-1-8",
          "3-1-10"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-1-10",
        "x": 0.659678217821782,
        "y": 0.6641895261845384,
        "name": "",
        "effect": "No parameter",
        "value": 0.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "3-1-9"
        ],
        "root": true,
        "description": ""
      },
      {
        "id": "3-1-11",
        "x": 0.40522277227722775,
        "y": 0.3869825436408977,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-1-6",
        "links": [
          "3-1-6",
          "3-1-12"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-1-12",
        "x": 0.33752475247524755,
        "y": 0.32483790523690764,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-1-11",
        "links": [
          "3-1-11",
          "3-1-13"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-1-13",
        "x": 0.27353960396039606,
        "y": 0.39985037406483787,
        "name": "",
        "effect": "No parameter",
        "value": 0.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "3-1-12"
        ],
        "root": true,
        "description": ""
      }
    ],
    "2": [
      {
        "id": "3-2-1",
        "x": 0.2995049504950495,
        "y": 0.49875311720698257,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": null,
        "links": [
          "3-2-2",
          "3-2-6",
          "3-2-9"
        ],
        "root": true,
        "description": ""
      },
      {
        "id": "3-2-2",
        "x": 0.40074257425742577,
        "y": 0.5014463840399002,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-2-1",
        "links": [
          "3-2-1",
          "3-2-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-2-3",
        "x": 0.5007425742574257,
        "y": 0.49915211970074796,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-2-2",
        "links": [
          "3-2-2",
          "3-2-4"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-2-4",
        "x": 0.6001237623762375,
        "y": 0.4993516209476308,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-2-3",
        "links": [
          "3-2-3",
          "3-2-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-2-5",
        "x": 0.7007425742574257,
        "y": 0.4970573566084787,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-2-4",
        "links": [
          "3-2-4",
          "3-2-8",
          "3-2-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-2-6",
        "x": 0.39331683168316833,
        "y": 0.6523192019950125,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-2-1",
        "links": [
          "3-2-1",
          "3-2-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-2-7",
        "x": 0.5013613861386139,
        "y": 0.6263341645885286,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-2-6",
        "links": [
          "3-2-6",
          "3-2-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-2-8",
        "x": 0.6112623762376239,
        "y": 0.6539650872817954,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-2-7",
        "links": [
          "3-2-7",
          "3-2-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-2-9",
        "x": 0.3896039603960396,
        "y": 0.33685785536159596,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-2-1",
        "links": [
          "3-2-1",
          "3-2-10"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-2-10",
        "x": 0.49950495049504945,
        "y": 0.36947630922693264,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-2-9",
        "links": [
          "3-2-9",
          "3-2-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-2-11",
        "x": 0.6100247524752475,
        "y": 0.3397506234413965,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-2-10",
        "links": [
          "3-2-10",
          "3-2-5"
        ],
        "root": false,
        "description": ""
      }
    ],
    "3": [
      {
        "id": "3-3-1",
        "x": 0.35457920792079206,
        "y": 0.5,
        "name": "Урон: +10%",
        "effect": "Generic Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "3-3-2",
          "3-3-5",
          "3-3-9"
        ],
        "root": true,
        "description": "Урон: +10%"
      },
      {
        "id": "3-3-2",
        "x": 0.3332920792079208,
        "y": 0.6323690773067331,
        "name": "Стихийный урон: +5%",
        "effect": "Elemental Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "3-3-1",
        "links": [
          "3-3-1",
          "3-3-3"
        ],
        "root": false,
        "description": "Стихийный урон: +5%"
      },
      {
        "id": "3-3-3",
        "x": 0.439480198019802,
        "y": 0.588927680798005,
        "name": "Стихийный урон: +20%",
        "effect": "Elemental Damage Increase",
        "value": 20.0,
        "type": "node",
        "parent_id": "3-3-2",
        "links": [
          "3-3-2",
          "3-3-4"
        ],
        "root": false,
        "description": "Стихийный урон: +20%"
      },
      {
        "id": "3-3-4",
        "x": 0.6316831683168317,
        "y": 0.6489775561097255,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-3-3",
        "links": [
          "3-3-3",
          "3-3-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-3-5",
        "x": 0.4205445544554456,
        "y": 0.41416458852867827,
        "name": "Урон в ближнем бою: +5%",
        "effect": "Melee Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "3-3-1",
        "links": [
          "3-3-1",
          "3-3-6"
        ],
        "root": false,
        "description": "Урон в ближнем бою: +5%"
      },
      {
        "id": "3-3-6",
        "x": 0.49950495049504956,
        "y": 0.47795511221945136,
        "name": "Урон в ближнем бою: +20%",
        "effect": "Melee Damage Increase",
        "value": 20.0,
        "type": "node",
        "parent_id": "3-3-5",
        "links": [
          "3-3-5",
          "3-3-7"
        ],
        "root": false,
        "description": "Урон в ближнем бою: +20%"
      },
      {
        "id": "3-3-7",
        "x": 0.5660891089108911,
        "y": 0.5367581047381547,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-3-6",
        "links": [
          "3-3-6",
          "3-3-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-3-8",
        "x": 0.6054455445544555,
        "y": 0.4085286783042394,
        "name": "Урон в ближнем бою: +8%(усиление)",
        "effect": "Melee Damage Amplification",
        "value": 8.0,
        "type": "node",
        "parent_id": "3-3-7",
        "links": [
          "3-3-7",
          "3-3-4",
          "3-3-11"
        ],
        "root": false,
        "description": "Урон в ближнем бою: +8%(усиление)"
      },
      {
        "id": "3-3-9",
        "x": 0.3141089108910891,
        "y": 0.32314214463840396,
        "name": "Физический урон: +5%",
        "effect": "Physical Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "3-3-1",
        "links": [
          "3-3-1",
          "3-3-10"
        ],
        "root": false,
        "description": "Физический урон: +5%"
      },
      {
        "id": "3-3-10",
        "x": 0.49269801980198025,
        "y": 0.3395511221945137,
        "name": "Физический урон: +20%",
        "effect": "Physical Damage Increase",
        "value": 20.0,
        "type": "node",
        "parent_id": "3-3-9",
        "links": [
          "3-3-9",
          "3-3-11"
        ],
        "root": false,
        "description": "Физический урон: +20%"
      },
      {
        "id": "3-3-11",
        "x": 0.6521039603960397,
        "y": 0.2948628428927681,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-3-10",
        "links": [
          "3-3-10",
          "3-3-8"
        ],
        "root": false,
        "description": ""
      }
    ],
    "4": [
      {
        "id": "3-4-1",
        "x": 0.3001237623762376,
        "y": 0.29800498753117205,
        "name": "Урон снаряда: +10%",
        "effect": "Projectile Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "3-4-2",
          "3-4-6",
          "3-4-9"
        ],
        "root": true,
        "description": "Урон снаряда: +10%"
      },
      {
        "id": "3-4-2",
        "x": 0.3964108910891089,
        "y": 0.44284289276807975,
        "name": "Урон снаряда: +5%",
        "effect": "Projectile Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "3-4-1",
        "links": [
          "3-4-1",
          "3-4-3"
        ],
        "root": false,
        "description": "Урон снаряда: +5%"
      },
      {
        "id": "3-4-3",
        "x": 0.50259900990099,
        "y": 0.4081296758104737,
        "name": "Урон снаряда: +20%",
        "effect": "Projectile Damage Increase",
        "value": 20.0,
        "type": "node",
        "parent_id": "3-4-2",
        "links": [
          "3-4-2",
          "3-4-4"
        ],
        "root": false,
        "description": "Урон снаряда: +20%"
      },
      {
        "id": "3-4-4",
        "x": 0.5784653465346533,
        "y": 0.379650872817955,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-4-3",
        "links": [
          "3-4-3",
          "3-4-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-4-5",
        "x": 0.6889851485148513,
        "y": 0.5431920199501246,
        "name": "Урон снаряда: +8%(усиление)",
        "effect": "Projectile Damage Amplification",
        "value": 8.0,
        "type": "node",
        "parent_id": "3-4-4",
        "links": [
          "3-4-4",
          "3-4-8",
          "3-4-11"
        ],
        "root": false,
        "description": "Урон снаряда: +8%(усиление)"
      },
      {
        "id": "3-4-6",
        "x": 0.3902227722772277,
        "y": 0.22463840399002494,
        "name": "Физический урон: +5%",
        "effect": "Physical Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "3-4-1",
        "links": [
          "3-4-1",
          "3-4-7"
        ],
        "root": false,
        "description": "Физический урон: +5%"
      },
      {
        "id": "3-4-7",
        "x": 0.492079207920792,
        "y": 0.2485286783042394,
        "name": "Физический урон: +20%",
        "effect": "Physical Damage Increase",
        "value": 20.0,
        "type": "node",
        "parent_id": "3-4-6",
        "links": [
          "3-4-6",
          "3-4-8"
        ],
        "root": false,
        "description": "Физический урон: +20%"
      },
      {
        "id": "3-4-8",
        "x": 0.586509900990099,
        "y": 0.22004987531172066,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-4-7",
        "links": [
          "3-4-7",
          "3-4-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-4-9",
        "x": 0.27636138613861383,
        "y": 0.4702743142144638,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "3-4-1",
        "links": [
          "3-4-1",
          "3-4-10"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "3-4-10",
        "x": 0.367079207920792,
        "y": 0.5627431421446384,
        "name": "Стихийный урон: +20%",
        "effect": "Elemental Damage Increase",
        "value": 20.0,
        "type": "node",
        "parent_id": "3-4-9",
        "links": [
          "3-4-9",
          "3-4-11"
        ],
        "root": false,
        "description": "Стихийный урон: +20%"
      },
      {
        "id": "3-4-11",
        "x": 0.5499999999999999,
        "y": 0.5255361596009974,
        "name": "Стихийный урон: +5%",
        "effect": "Elemental Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "3-4-10",
        "links": [
          "3-4-10",
          "3-4-5"
        ],
        "root": false,
        "description": "Стихийный урон: +5%"
      }
    ]
  },
  "4": {
    "1": [
      {
        "id": "4-1-1",
        "x": 0.20017326732673268,
        "y": 0.5035910224438903,
        "name": "Урон при атаке: +5%",
        "effect": "Attack Damage Increase",
        "type": "node",
        "parent_id": null,
        "root": true,
        "links": [
          "4-1-2",
          "4-1-6",
          "4-1-7",
          "4-1-8"
        ],
        "value": 5.0,
        "description": "Урон при атаке: +5%"
      },
      {
        "id": "4-1-2",
        "x": 0.2616831683168317,
        "y": 0.3,
        "name": "",
        "effect": "",
        "type": "node",
        "parent_id": "4-1-1",
        "root": false,
        "links": [
          "4-1-1",
          "4-1-3"
        ],
        "value": 0,
        "description": ""
      },
      {
        "id": "4-1-3",
        "x": 0.40004950495049507,
        "y": 0.33511221945137154,
        "name": "Урон при атаке: +10%",
        "effect": "Attack Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": "4-1-2",
        "links": [
          "4-1-2",
          "4-1-4",
          "4-1-6",
          "4-1-7",
          "4-1-8",
          "4-1-9",
          "4-1-10"
        ],
        "root": false,
        "description": "Урон при атаке: +10%"
      },
      {
        "id": "4-1-4",
        "x": 0.5019059405940595,
        "y": 0.25052369077306735,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-1-3",
        "links": [
          "4-1-3",
          "4-1-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-1-5",
        "x": 0.6031435643564357,
        "y": 0.27690773067331675,
        "name": "Урон при атаке: +40%",
        "effect": "Attack Damage Increase",
        "value": 40.0,
        "type": "node",
        "parent_id": "4-1-4",
        "links": [
          "4-1-4",
          "4-1-9",
          "4-1-10"
        ],
        "root": false,
        "description": "Урон при атаке: +40%"
      },
      {
        "id": "4-1-6",
        "x": 0.2946039603960396,
        "y": 0.40778054862842894,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-1-1",
        "links": [
          "4-1-1",
          "4-1-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-1-7",
        "x": 0.33297029702970293,
        "y": 0.4863341645885287,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-1-1",
        "links": [
          "4-1-1",
          "4-1-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-1-8",
        "x": 0.37999999999999995,
        "y": 0.5773566084788031,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-1-1",
        "links": [
          "4-1-1",
          "4-1-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-1-9",
        "x": 0.5248019801980198,
        "y": 0.3664837905236908,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-1-3",
        "links": [
          "4-1-3",
          "4-1-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-1-10",
        "x": 0.5390346534653465,
        "y": 0.46748129675810474,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-1-3",
        "links": [
          "4-1-3",
          "4-1-5"
        ],
        "root": false,
        "description": ""
      }
    ],
    "2": [
      {
        "id": "4-2-1",
        "x": 0.24876237623762376,
        "y": 0.300498753117207,
        "name": "Урон при использовании заклинания: +5%",
        "effect": "Spell Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "4-2-2",
          "4-2-4",
          "4-2-5",
          "4-2-6"
        ],
        "root": true,
        "description": "Урон при использовании заклинания: +5%"
      },
      {
        "id": "4-2-2",
        "x": 0.38403465346534654,
        "y": 0.25955112219451376,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-2-1",
        "links": [
          "4-2-1",
          "4-2-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-2-3",
        "x": 0.45495049504950497,
        "y": 0.42807980049875316,
        "name": "Урон при использовании заклинания: +10%",
        "effect": "Spell Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": "4-2-2",
        "links": [
          "4-2-2",
          "4-2-4",
          "4-2-5",
          "4-2-6",
          "4-2-7",
          "4-2-9",
          "4-2-10"
        ],
        "root": false,
        "description": "Урон при использовании заклинания: +10%"
      },
      {
        "id": "4-2-4",
        "x": 0.33514851485148517,
        "y": 0.33062344139650873,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-2-1",
        "links": [
          "4-2-1",
          "4-2-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-2-5",
        "x": 0.3611386138613861,
        "y": 0.4440897755610973,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-2-1",
        "links": [
          "4-2-1",
          "4-2-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-2-6",
        "x": 0.3580445544554456,
        "y": 0.5438403990024938,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-2-1",
        "links": [
          "4-2-1",
          "4-2-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-2-7",
        "x": 0.5574257425742574,
        "y": 0.283640897755611,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-2-3",
        "links": [
          "4-2-3",
          "4-2-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-2-8",
        "x": 0.6667079207920791,
        "y": 0.5232418952618454,
        "name": "Урон при использовании заклинания: +40%",
        "effect": "Spell Damage Increase",
        "value": 40.0,
        "type": "node",
        "parent_id": "4-2-7",
        "links": [
          "4-2-7",
          "4-2-9",
          "4-2-10"
        ],
        "root": false,
        "description": "Урон при использовании заклинания: +40%"
      },
      {
        "id": "4-2-9",
        "x": 0.5728960396039604,
        "y": 0.4020947630922693,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-2-3",
        "links": [
          "4-2-3",
          "4-2-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-2-10",
        "x": 0.5741336633663366,
        "y": 0.5280299251870324,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-2-3",
        "links": [
          "4-2-3",
          "4-2-8"
        ],
        "root": false,
        "description": ""
      }
    ],
    "3": [
      {
        "id": "4-3-1",
        "x": 0.24566831683168316,
        "y": 0.5498753117206983,
        "name": "Урон по области: +10%",
        "effect": "Area Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "4-3-2",
          "4-3-4",
          "4-3-5",
          "4-3-6"
        ],
        "root": true,
        "description": "Урон по области: +10%"
      },
      {
        "id": "4-3-2",
        "x": 0.2831683168316832,
        "y": 0.29820448877805483,
        "name": "Физический урон: +10%",
        "effect": "Physical Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": "4-3-1",
        "links": [
          "4-3-1",
          "4-3-3"
        ],
        "root": false,
        "description": "Физический урон: +10%"
      },
      {
        "id": "4-3-3",
        "x": 0.4648514851485149,
        "y": 0.31835411471321695,
        "name": "Урон по области: +5%",
        "effect": "Area Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "4-3-2",
        "links": [
          "4-3-2",
          "4-3-4",
          "4-3-5",
          "4-3-6",
          "4-3-7",
          "4-3-9",
          "4-3-10",
          "4-3-11"
        ],
        "root": false,
        "description": "Урон по области: +5%"
      },
      {
        "id": "4-3-4",
        "x": 0.31225247524752475,
        "y": 0.42788029925187027,
        "name": "Урон в ближнем бою: +10%",
        "effect": "Melee Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": "4-3-1",
        "links": [
          "4-3-1",
          "4-3-3"
        ],
        "root": false,
        "description": "Урон в ближнем бою: +10%"
      },
      {
        "id": "4-3-5",
        "x": 0.3803217821782178,
        "y": 0.4540648379052369,
        "name": "Урон снаряда: +10%",
        "effect": "Projectile Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": "4-3-1",
        "links": [
          "4-3-1",
          "4-3-3"
        ],
        "root": false,
        "description": "Урон снаряда: +10%"
      },
      {
        "id": "4-3-6",
        "x": 0.3889851485148515,
        "y": 0.6149127182044888,
        "name": "Стихийный урон: +10%",
        "effect": "Elemental Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": "4-3-1",
        "links": [
          "4-3-1",
          "4-3-3"
        ],
        "root": false,
        "description": "Стихийный урон: +10%"
      },
      {
        "id": "4-3-7",
        "x": 0.5988861386138614,
        "y": 0.27117206982543646,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-3-3",
        "links": [
          "4-3-3",
          "4-3-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-3-8",
        "x": 0.6846534653465347,
        "y": 0.464638403990025,
        "name": "Урон по области: +5%(усиление)",
        "effect": "Area Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "4-3-7",
        "links": [
          "4-3-7",
          "4-3-9",
          "4-3-10",
          "4-3-11"
        ],
        "root": false,
        "description": "Урон по области: +5%(усиление)"
      },
      {
        "id": "4-3-9",
        "x": 0.6019801980198021,
        "y": 0.3808977556109726,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-3-3",
        "links": [
          "4-3-3",
          "4-3-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-3-10",
        "x": 0.5543316831683169,
        "y": 0.45072319201995015,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-3-3",
        "links": [
          "4-3-3",
          "4-3-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-3-11",
        "x": 0.528960396039604,
        "y": 0.5542144638403991,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-3-3",
        "links": [
          "4-3-3",
          "4-3-8"
        ],
        "root": false,
        "description": ""
      }
    ],
    "4": [
      {
        "id": "4-4-1",
        "x": 0.3415841584158416,
        "y": 0.6508728179551122,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": null,
        "links": [
          "4-4-2",
          "4-4-4"
        ],
        "root": true,
        "description": ""
      },
      {
        "id": "4-4-2",
        "x": 0.3728960396039604,
        "y": 0.479002493765586,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-4-1",
        "links": [
          "4-4-1",
          "4-4-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-4-3",
        "x": 0.49579207920792084,
        "y": 0.4455361596009974,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-4-2",
        "links": [
          "4-4-2",
          "4-4-4",
          "4-4-5",
          "4-4-6",
          "4-4-8",
          "4-4-10"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-4-4",
        "x": 0.44777227722772284,
        "y": 0.6323690773067331,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-4-1",
        "links": [
          "4-4-1",
          "4-4-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-4-5",
        "x": 0.5568069306930693,
        "y": 0.6340149625935162,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-4-3",
        "links": [
          "4-4-3",
          "4-4-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-4-6",
        "x": 0.6155940594059408,
        "y": 0.4706733167082293,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-4-3",
        "links": [
          "4-4-3",
          "4-4-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-4-7",
        "x": 0.6741336633663368,
        "y": 0.6367082294264337,
        "name": "",
        "effect": "No parameter",
        "value": 0.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "4-4-6",
          "4-4-5"
        ],
        "root": true,
        "description": ""
      },
      {
        "id": "4-4-8",
        "x": 0.4274752475247526,
        "y": 0.3185536159600996,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-4-3",
        "links": [
          "4-4-3",
          "4-4-9"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-4-9",
        "x": 0.4952970297029704,
        "y": 0.2539152119700747,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-4-8",
        "links": [
          "4-4-8",
          "4-4-10"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-4-10",
        "x": 0.5631188118811883,
        "y": 0.3251870324189526,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-4-9",
        "links": [
          "4-4-9",
          "4-4-3"
        ],
        "root": false,
        "description": ""
      }
    ],
    "5": [
      {
        "id": "4-5-1",
        "x": 0.2995049504950495,
        "y": 0.6982543640897756,
        "name": "Стихийный урон: +5%",
        "effect": "Elemental Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "4-5-2",
          "4-5-4"
        ],
        "root": true,
        "description": "Стихийный урон: +5%"
      },
      {
        "id": "4-5-2",
        "x": 0.34133663366336636,
        "y": 0.5725187032418952,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-5-1",
        "links": [
          "4-5-1",
          "4-5-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-5-3",
        "x": 0.4283415841584159,
        "y": 0.5315710723192019,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-5-2",
        "links": [
          "4-5-2",
          "4-5-4",
          "4-5-5",
          "4-5-7",
          "4-5-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-5-4",
        "x": 0.4045792079207922,
        "y": 0.6888778054862841,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-5-3",
        "links": [
          "4-5-3",
          "4-5-1"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-5-5",
        "x": 0.5277227722772279,
        "y": 0.5404987531172067,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-5-3",
        "links": [
          "4-5-3",
          "4-5-6"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-5-6",
        "x": 0.6561881188118812,
        "y": 0.6392019950124684,
        "name": "Стихийный урон: +5%",
        "effect": "Elemental Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "4-5-5",
          "4-5-7"
        ],
        "root": true,
        "description": "Стихийный урон: +5%"
      },
      {
        "id": "4-5-7",
        "x": 0.5334158415841586,
        "y": 0.690523690773067,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-5-6",
        "links": [
          "4-5-6",
          "4-5-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-5-8",
        "x": 0.37301980198019813,
        "y": 0.4370074812967579,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-5-3",
        "links": [
          "4-5-3",
          "4-5-9"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-5-9",
        "x": 0.2991336633663367,
        "y": 0.36239401496259327,
        "name": "Стихийный урон: +5%(усиление)",
        "effect": "Elemental Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "4-5-8",
        "links": [
          "4-5-8",
          "4-5-10"
        ],
        "root": false,
        "description": "Стихийный урон: +5%(усиление)"
      },
      {
        "id": "4-5-10",
        "x": 0.3966584158415842,
        "y": 0.3426433915211968,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-5-9",
        "links": [
          "4-5-9",
          "4-5-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-5-11",
        "x": 0.5053217821782179,
        "y": 0.34783042394014946,
        "name": "Стихийный урон: +10%",
        "effect": "Elemental Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": "4-5-10",
        "links": [
          "4-5-10",
          "4-5-12",
          "4-5-13"
        ],
        "root": false,
        "description": "Стихийный урон: +10%"
      },
      {
        "id": "4-5-12",
        "x": 0.5985148514851485,
        "y": 0.3181047381546133,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-5-11",
        "links": [
          "4-5-11",
          "4-5-15"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-5-13",
        "x": 0.6022277227722772,
        "y": 0.4452867830423939,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-5-11",
        "links": [
          "4-5-11",
          "4-5-14"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-5-14",
        "x": 0.6954207920792079,
        "y": 0.449226932668329,
        "name": "Стихийный урон: +5%",
        "effect": "Elemental Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "4-5-13"
        ],
        "root": true,
        "description": "Стихийный урон: +5%"
      },
      {
        "id": "4-5-15",
        "x": 0.6997524752475247,
        "y": 0.33825436408977544,
        "name": "Стихийный урон: +5%",
        "effect": "Elemental Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "4-5-12"
        ],
        "root": true,
        "description": "Стихийный урон: +5%"
      }
    ],
    "6": [
      {
        "id": "4-6-1",
        "x": 0.3001237623762376,
        "y": 0.6982543640897756,
        "name": "Физический урон: +5%",
        "effect": "Physical Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "4-6-2",
          "4-6-4"
        ],
        "root": true,
        "description": "Физический урон: +5%"
      },
      {
        "id": "4-6-2",
        "x": 0.34443069306930685,
        "y": 0.5463341645885287,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-6-1",
        "links": [
          "4-6-1",
          "4-6-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-6-3",
        "x": 0.43019801980198014,
        "y": 0.5402992518703241,
        "name": "Физический урон: +5%",
        "effect": "Physical Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "4-6-2",
        "links": [
          "4-6-2",
          "4-6-4",
          "4-6-5",
          "4-6-7",
          "4-6-8"
        ],
        "root": false,
        "description": "Физический урон: +5%"
      },
      {
        "id": "4-6-4",
        "x": 0.40507425742574255,
        "y": 0.6897256857855362,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-6-1",
        "links": [
          "4-6-1",
          "4-6-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-6-5",
        "x": 0.5431930693069306,
        "y": 0.5766583541147132,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-6-3",
        "links": [
          "4-6-3",
          "4-6-6"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-6-6",
        "x": 0.6431930693069305,
        "y": 0.6566583541147132,
        "name": "Физический урон: +5%",
        "effect": "Physical Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "4-6-5",
          "4-6-7"
        ],
        "root": true,
        "description": "Физический урон: +5%"
      },
      {
        "id": "4-6-7",
        "x": 0.5444306930693068,
        "y": 0.712568578553616,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-6-3",
        "links": [
          "4-6-3",
          "4-6-6"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-6-8",
        "x": 0.37797029702970286,
        "y": 0.437007481296758,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-6-3",
        "links": [
          "4-6-3",
          "4-6-9"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-6-9",
        "x": 0.3288366336633662,
        "y": 0.34743142144638395,
        "name": "Физический урон: +5%(усиление)",
        "effect": "Physical Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "4-6-8",
        "links": [
          "4-6-8",
          "4-6-10"
        ],
        "root": false,
        "description": "Физический урон: +5%(усиление)"
      },
      {
        "id": "4-6-10",
        "x": 0.4214108910891088,
        "y": 0.3463840399002493,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-6-9",
        "links": [
          "4-6-9",
          "4-6-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-6-11",
        "x": 0.5053217821782177,
        "y": 0.3652867830423939,
        "name": "Физический урон: +10%",
        "effect": "Physical Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": "4-6-10",
        "links": [
          "4-6-10",
          "4-6-12",
          "4-6-14"
        ],
        "root": false,
        "description": "Физический урон: +10%"
      },
      {
        "id": "4-6-12",
        "x": 0.5978960396039602,
        "y": 0.3904239401496259,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-6-11",
        "links": [
          "4-6-11",
          "4-6-13"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-6-13",
        "x": 0.6737623762376236,
        "y": 0.3357605985037406,
        "name": "Физический урон: +5%",
        "effect": "Physical Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "4-6-12"
        ],
        "root": true,
        "description": "Физический урон: +5%"
      },
      {
        "id": "4-6-14",
        "x": 0.5985148514851484,
        "y": 0.46024937655860343,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "4-6-11",
        "links": [
          "4-6-11",
          "4-6-15"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "4-6-15",
        "x": 0.6793316831683167,
        "y": 0.5003491271820448,
        "name": "Физический урон: +5%",
        "effect": "Physical Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "4-6-14"
        ],
        "root": true,
        "description": "Физический урон: +5%"
      }
    ]
  },
  "5": {
    "1": [
      {
        "id": "5-1-1",
        "x": 0.1967821782178218,
        "y": 0.49835411471321694,
        "name": "Урон при использовании заклинания: +10%",
        "effect": "Spell Damage Increase",
        "type": "node",
        "parent_id": null,
        "value": 10.0,
        "links": [
          "5-1-2",
          "5-1-6",
          "5-1-9",
          "5-1-12"
        ],
        "root": true,
        "description": "Урон при использовании заклинания: +10%"
      },
      {
        "id": "5-1-2",
        "x": 0.2831683168316832,
        "y": 0.3439401496259351,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-1-1",
        "links": [
          "5-1-1",
          "5-1-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-1-3",
        "x": 0.4023514851485149,
        "y": 0.32418952618453856,
        "name": "Урон при использовании заклинания: +5%",
        "effect": "Spell Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "5-1-2",
        "links": [
          "5-1-2",
          "5-1-4"
        ],
        "root": false,
        "description": "Урон при использовании заклинания: +5%"
      },
      {
        "id": "5-1-4",
        "x": 0.5586633663366337,
        "y": 0.3368578553615959,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-1-3",
        "links": [
          "5-1-3",
          "5-1-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-1-5",
        "x": 0.6660891089108911,
        "y": 0.4230922693266832,
        "name": "Повышает УРН при использовании заклинания: +5%",
        "effect": "Spell Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "5-1-4",
        "links": [
          "5-1-4",
          "5-1-8",
          "5-1-11",
          "5-1-14"
        ],
        "root": false,
        "description": "Повышает УРН при использовании заклинания: +5%"
      },
      {
        "id": "5-1-6",
        "x": 0.3431930693069308,
        "y": 0.4499251870324189,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-1-1",
        "links": [
          "5-1-1",
          "5-1-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-1-7",
        "x": 0.4599009900990099,
        "y": 0.41022443890274307,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-1-6",
        "links": [
          "5-1-6",
          "5-1-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-1-8",
        "x": 0.5586633663366337,
        "y": 0.44907730673316704,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-1-7",
        "links": [
          "5-1-7",
          "5-1-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-1-9",
        "x": 0.3023514851485149,
        "y": 0.5446882793017456,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-1-1",
        "links": [
          "5-1-1",
          "5-1-10"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-1-10",
        "x": 0.4277227722772278,
        "y": 0.511221945137157,
        "name": "Урон при использовании заклинания: +5%",
        "effect": "Spell Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "5-1-9",
        "links": [
          "5-1-9",
          "5-1-11"
        ],
        "root": false,
        "description": "Урон при использовании заклинания: +5%"
      },
      {
        "id": "5-1-11",
        "x": 0.5357673267326734,
        "y": 0.5276309226932667,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-1-10",
        "links": [
          "5-1-10",
          "5-1-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-1-12",
        "x": 0.2936881188118812,
        "y": 0.6431920199501245,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-1-1",
        "links": [
          "5-1-1",
          "5-1-13"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-1-13",
        "x": 0.46485148514851493,
        "y": 0.623441396508728,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-1-12",
        "links": [
          "5-1-12",
          "5-1-14"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-1-14",
        "x": 0.5883663366336634,
        "y": 0.6124189526184537,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-1-13",
        "links": [
          "5-1-13",
          "5-1-5"
        ],
        "root": false,
        "description": ""
      }
    ],
    "2": [
      {
        "id": "5-2-1",
        "x": 0.1998762376237624,
        "y": 0.5,
        "name": "Урон при атаке: +10%",
        "effect": "Attack Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "5-2-2",
          "5-2-6",
          "5-2-9",
          "5-2-12"
        ],
        "root": true,
        "description": "Урон при атаке: +10%"
      },
      {
        "id": "5-2-2",
        "x": 0.26769801980198016,
        "y": 0.34433915211970073,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-2-1",
        "links": [
          "5-2-1",
          "5-2-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-2-3",
        "x": 0.408539603960396,
        "y": 0.345785536159601,
        "name": "Урон при атаке: +5%",
        "effect": "Attack Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "5-2-2",
        "links": [
          "5-2-2",
          "5-2-4"
        ],
        "root": false,
        "description": "Урон при атаке: +5%"
      },
      {
        "id": "5-2-4",
        "x": 0.5549504950495049,
        "y": 0.3497256857855362,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-2-3",
        "links": [
          "5-2-3",
          "5-2-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-2-5",
        "x": 0.6883663366336633,
        "y": 0.46837905236907734,
        "name": "Повышает УРН при атаке: +5%",
        "effect": "Attack Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "5-2-4",
        "links": [
          "5-2-4",
          "5-2-8",
          "5-2-11",
          "5-2-14"
        ],
        "root": false,
        "description": "Повышает УРН при атаке: +5%"
      },
      {
        "id": "5-2-6",
        "x": 0.3165841584158416,
        "y": 0.4228927680798005,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-2-1",
        "links": [
          "5-2-1",
          "5-2-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-2-7",
        "x": 0.46670792079207923,
        "y": 0.4293266832917705,
        "name": "Урон при атаке: +5%",
        "effect": "Attack Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "5-2-6",
        "links": [
          "5-2-6",
          "5-2-8"
        ],
        "root": false,
        "description": "Урон при атаке: +5%"
      },
      {
        "id": "5-2-8",
        "x": 0.5951732673267326,
        "y": 0.45571072319201983,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-2-7",
        "links": [
          "5-2-7",
          "5-2-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-2-9",
        "x": 0.3004950495049505,
        "y": 0.5538154613466335,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-2-1",
        "links": [
          "5-2-1",
          "5-2-10"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-2-10",
        "x": 0.40792079207920795,
        "y": 0.5278304239401496,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-2-9",
        "links": [
          "5-2-9",
          "5-2-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-2-11",
        "x": 0.5351485148514852,
        "y": 0.5592019950124687,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-2-10",
        "links": [
          "5-2-10",
          "5-2-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-2-12",
        "x": 0.27636138613861383,
        "y": 0.6573067331670822,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-2-1",
        "links": [
          "5-2-1",
          "5-2-13"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-2-13",
        "x": 0.44938118811881184,
        "y": 0.6313216957605984,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-2-12",
        "links": [
          "5-2-12",
          "5-2-14"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-2-14",
        "x": 0.6069306930693069,
        "y": 0.6564588528678303,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-2-13",
        "links": [
          "5-2-13",
          "5-2-5"
        ],
        "root": false,
        "description": ""
      }
    ],
    "3": [
      {
        "id": "5-3-1",
        "x": 0.3001237623762376,
        "y": 0.5,
        "name": "Урон: +15%",
        "effect": "Generic Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "5-3-2",
          "5-3-6",
          "5-3-9"
        ],
        "root": true,
        "description": "Урон: +15%"
      },
      {
        "id": "5-3-2",
        "x": 0.40012376237623765,
        "y": 0.5001995012468827,
        "name": "Урон: +5%",
        "effect": "Generic Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "5-3-1",
        "links": [
          "5-3-1",
          "5-3-3"
        ],
        "root": false,
        "description": "Урон: +5%"
      },
      {
        "id": "5-3-3",
        "x": 0.5007425742574257,
        "y": 0.5003990024937655,
        "name": "Урон: +30%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 30.0,
        "type": "node",
        "parent_id": "5-3-2",
        "links": [
          "5-3-2",
          "5-3-4"
        ],
        "root": false,
        "description": "Урон: +30%(усиление)"
      },
      {
        "id": "5-3-4",
        "x": 0.6007425742574257,
        "y": 0.5005985037406482,
        "name": "Урон: +5%",
        "effect": "Generic Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "5-3-3",
        "links": [
          "5-3-3",
          "5-3-5"
        ],
        "root": false,
        "description": "Урон: +5%"
      },
      {
        "id": "5-3-5",
        "x": 0.7013613861386138,
        "y": 0.5007980049875309,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-3-4",
        "links": [
          "5-3-4",
          "5-3-8",
          "5-3-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-3-6",
        "x": 0.40383663366336636,
        "y": 0.33685785536159596,
        "name": "Критический УРН: +10%",
        "effect": "Critical Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": "5-3-1",
        "links": [
          "5-3-1",
          "5-3-7"
        ],
        "root": false,
        "description": "Критический УРН: +10%"
      },
      {
        "id": "5-3-7",
        "x": 0.49950495049504956,
        "y": 0.3682294264339152,
        "name": "Критический УРН: +10%",
        "effect": "Critical Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": "5-3-6",
        "links": [
          "5-3-6",
          "5-3-8"
        ],
        "root": false,
        "description": "Критический УРН: +10%"
      },
      {
        "id": "5-3-8",
        "x": 0.601361386138614,
        "y": 0.34224438902743143,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "5-3-7",
        "links": [
          "5-3-7",
          "5-3-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "5-3-9",
        "x": 0.40507425742574255,
        "y": 0.6510723192019949,
        "name": "Максимальный УРН: +5%",
        "effect": "Double Maximum Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "5-3-1",
        "links": [
          "5-3-1",
          "5-3-10"
        ],
        "root": false,
        "description": "Максимальный УРН: +5%"
      },
      {
        "id": "5-3-10",
        "x": 0.5001237623762376,
        "y": 0.6238403990024937,
        "name": "Максимальный УРН: +5%",
        "effect": "Double Maximum Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "5-3-9",
        "links": [
          "5-3-9",
          "5-3-11"
        ],
        "root": false,
        "description": "Максимальный УРН: +5%"
      },
      {
        "id": "5-3-11",
        "x": 0.60259900990099,
        "y": 0.6664339152119699,
        "name": "Максимальный УРН: +5%",
        "effect": "Double Maximum Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "5-3-10",
        "links": [
          "5-3-10",
          "5-3-5"
        ],
        "root": false,
        "description": "Максимальный УРН: +5%"
      }
    ]
  },
  "6": {
    "1": [
      {
        "id": "6-1-1",
        "x": 0.4993811881188119,
        "y": 0.4048628428927681,
        "name": "",
        "effect": "",
        "type": "node",
        "parent_id": null,
        "value": 0,
        "links": [
          "6-1-2",
          "6-1-6",
          "6-1-10",
          "6-1-14",
          "6-1-18",
          "6-1-22"
        ],
        "root": true,
        "description": ""
      },
      {
        "id": "6-1-2",
        "x": 0.42425742574257425,
        "y": 0.32401496259351625,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-1",
        "links": [
          "6-1-1",
          "6-1-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-3",
        "x": 0.32623762376237625,
        "y": 0.2606234413965088,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-2",
        "links": [
          "6-1-2",
          "6-1-4"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-4",
        "x": 0.23935643564356432,
        "y": 0.28825436408977556,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-3",
        "links": [
          "6-1-3",
          "6-1-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-5",
        "x": 0.16856435643564355,
        "y": 0.24730673316708232,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-4",
        "links": [
          "6-1-4"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-6",
        "x": 0.4292079207920792,
        "y": 0.45119700748129676,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-1",
        "links": [
          "6-1-1",
          "6-1-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-7",
        "x": 0.34851485148514855,
        "y": 0.39778054862842893,
        "name": "Урон по области: +20%",
        "effect": "Area Damage Increase",
        "value": 20.0,
        "type": "node",
        "parent_id": "6-1-6",
        "links": [
          "6-1-6",
          "6-1-8"
        ],
        "root": false,
        "description": "Урон по области: +20%"
      },
      {
        "id": "6-1-8",
        "x": 0.257920792079208,
        "y": 0.3979800498753117,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-7",
        "links": [
          "6-1-7",
          "6-1-9"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-9",
        "x": 0.1679455445544555,
        "y": 0.37448877805486286,
        "name": "Урон по области: +6%(усиление)",
        "effect": "Area Damage Amplification",
        "value": 6.0,
        "type": "node",
        "parent_id": "6-1-8",
        "links": [
          "6-1-8"
        ],
        "root": false,
        "description": "Урон по области: +6%(усиление)"
      },
      {
        "id": "6-1-10",
        "x": 0.5077970297029704,
        "y": 0.5247630922693267,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-1",
        "links": [
          "6-1-1",
          "6-1-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-11",
        "x": 0.3726485148514852,
        "y": 0.5262094763092269,
        "name": "Урон от удара: +20%",
        "effect": "Strike Damage Increase",
        "value": 20.0,
        "type": "node",
        "parent_id": "6-1-10",
        "links": [
          "6-1-10",
          "6-1-12"
        ],
        "root": false,
        "description": "Урон от удара: +20%"
      },
      {
        "id": "6-1-12",
        "x": 0.27772277227722775,
        "y": 0.5226683291770573,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-11",
        "links": [
          "6-1-11",
          "6-1-13"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-13",
        "x": 0.17599009900990098,
        "y": 0.5291022443890273,
        "name": "Урон от удара: +6%(усиление)",
        "effect": "Strike Damage Amplification",
        "value": 6.0,
        "type": "node",
        "parent_id": "6-1-12",
        "links": [
          "6-1-12"
        ],
        "root": false,
        "description": "Урон от удара: +6%(усиление)"
      },
      {
        "id": "6-1-14",
        "x": 0.48737623762376237,
        "y": 0.2703990024937656,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-1",
        "links": [
          "6-1-1",
          "6-1-15"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-15",
        "x": 0.606559405940594,
        "y": 0.239426433915212,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-14",
        "links": [
          "6-1-14",
          "6-1-16"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-16",
        "x": 0.7133663366336633,
        "y": 0.23962593516209485,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-15",
        "links": [
          "6-1-15",
          "6-1-17"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-17",
        "x": 0.8139851485148514,
        "y": 0.25852867830423953,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-16",
        "links": [
          "6-1-16"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-18",
        "x": 0.5740099009900991,
        "y": 0.3539401496259352,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-1",
        "links": [
          "6-1-1",
          "6-1-19"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-19",
        "x": 0.6597772277227723,
        "y": 0.4002743142144638,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-18",
        "links": [
          "6-1-18",
          "6-1-20"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-20",
        "x": 0.7486386138613861,
        "y": 0.37802992518703243,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-19",
        "links": [
          "6-1-19",
          "6-1-21"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-21",
        "x": 0.8282178217821782,
        "y": 0.41812967581047383,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-20",
        "links": [
          "6-1-20"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-22",
        "x": 0.5789603960396039,
        "y": 0.4761346633416459,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-1",
        "links": [
          "6-1-1",
          "6-1-23"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-23",
        "x": 0.643069306930693,
        "y": 0.5112468827930174,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-22",
        "links": [
          "6-1-22",
          "6-1-24"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-24",
        "x": 0.7344059405940593,
        "y": 0.5376309226932667,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-23",
        "links": [
          "6-1-23",
          "6-1-25"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-1-25",
        "x": 0.8245049504950495,
        "y": 0.5241147132169575,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-1-24",
        "links": [
          "6-1-24"
        ],
        "root": false,
        "description": ""
      }
    ],
    "2": [
      {
        "id": "6-2-1",
        "x": 0.2995049504950495,
        "y": 0.7007481296758105,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": null,
        "links": [
          "6-2-2"
        ],
        "root": true,
        "description": ""
      },
      {
        "id": "6-2-2",
        "x": 0.40693069306930696,
        "y": 0.6847381546134663,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-2-1",
        "links": [
          "6-2-1",
          "6-2-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-2-3",
        "x": 0.5131188118811881,
        "y": 0.6911720698254363,
        "name": "Стихийный урон: +5%(усиление)",
        "effect": "Elemental Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "6-2-2",
        "links": [
          "6-2-2",
          "6-2-4"
        ],
        "root": false,
        "description": "Стихийный урон: +5%(усиление)"
      },
      {
        "id": "6-2-4",
        "x": 0.6118811881188119,
        "y": 0.693865336658354,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-2-3",
        "links": [
          "6-2-3",
          "6-2-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-2-5",
        "x": 0.707549504950495,
        "y": 0.6491770573566084,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-2-4",
        "links": [
          "6-2-4",
          "6-2-6",
          "6-2-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-2-6",
        "x": 0.7165841584158414,
        "y": 0.38129675810473795,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-2-5",
        "links": [
          "6-2-5",
          "6-2-7",
          "6-2-12"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-2-7",
        "x": 0.8017326732673266,
        "y": 0.3415960099750621,
        "name": "Урон: +5%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "6-2-6",
        "links": [
          "6-2-6"
        ],
        "root": false,
        "description": "Урон: +5%(усиление)"
      },
      {
        "id": "6-2-8",
        "x": 0.6138613861386137,
        "y": 0.5571072319201993,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-2-5",
        "links": [
          "6-2-5",
          "6-2-9"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-2-9",
        "x": 0.5275990099009897,
        "y": 0.557306733167082,
        "name": "Физический урон: +5%(усиление)",
        "effect": "Physical Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "6-2-8",
        "links": [
          "6-2-8",
          "6-2-10"
        ],
        "root": false,
        "description": "Физический урон: +5%(усиление)"
      },
      {
        "id": "6-2-10",
        "x": 0.4159653465346532,
        "y": 0.5587531172069822,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-2-9",
        "links": [
          "6-2-9",
          "6-2-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-2-11",
        "x": 0.31423267326732657,
        "y": 0.5614463840398999,
        "name": "",
        "effect": "No parameter",
        "value": 0.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "6-2-10"
        ],
        "root": true,
        "description": ""
      },
      {
        "id": "6-2-12",
        "x": 0.6278465346534652,
        "y": 0.3141645885286781,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-2-6",
        "links": [
          "6-2-6",
          "6-2-13",
          "6-2-17"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-2-13",
        "x": 0.576237623762376,
        "y": 0.4191022443890273,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-2-12",
        "links": [
          "6-2-12",
          "6-2-14"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-2-14",
        "x": 0.4800742574257423,
        "y": 0.4055860349127181,
        "name": "Стихийный урон: +15%",
        "effect": "Elemental Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "6-2-13",
        "links": [
          "6-2-13",
          "6-2-15"
        ],
        "root": false,
        "description": "Стихийный урон: +15%"
      },
      {
        "id": "6-2-15",
        "x": 0.39814356435643533,
        "y": 0.40204488778054853,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-2-14",
        "links": [
          "6-2-14",
          "6-2-16"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-2-16",
        "x": 0.30012376237623734,
        "y": 0.3997506234413964,
        "name": "Стихийный урон: +10%",
        "effect": "Elemental Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "6-2-15"
        ],
        "root": true,
        "description": "Стихийный урон: +10%"
      },
      {
        "id": "6-2-17",
        "x": 0.5428217821782175,
        "y": 0.31436408977556096,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-2-12",
        "links": [
          "6-2-12",
          "6-2-18"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-2-18",
        "x": 0.45346534653465315,
        "y": 0.2971072319201994,
        "name": "Физический урон: +15%",
        "effect": "Physical Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "6-2-17",
        "links": [
          "6-2-17",
          "6-2-19"
        ],
        "root": false,
        "description": "Физический урон: +15%"
      },
      {
        "id": "6-2-19",
        "x": 0.3665841584158413,
        "y": 0.29855361596009966,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "6-2-18",
        "links": [
          "6-2-18",
          "6-2-20"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "6-2-20",
        "x": 0.2896039603960393,
        "y": 0.28628428927680794,
        "name": "Физический урон: +10%",
        "effect": "Physical Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "6-2-19"
        ],
        "root": true,
        "description": "Физический урон: +10%"
      }
    ]
  },
  "7": {
    "1": [
      {
        "id": "7-1-1",
        "x": 0.501039603960396,
        "y": 0.4983790523690773,
        "name": "Урон от удара: +10%",
        "effect": "Strike Damage Increase",
        "type": "node",
        "parent_id": null,
        "value": 10.0,
        "links": [
          "7-1-2",
          "7-1-6",
          "7-1-10"
        ],
        "root": true,
        "description": "Урон от удара: +10%"
      },
      {
        "id": "7-1-2",
        "x": 0.41972772277227727,
        "y": 0.31778054862842886,
        "name": "Стихийный урон: +5%",
        "effect": "Elemental Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-1-1",
        "links": [
          "7-1-1",
          "7-1-3"
        ],
        "root": false,
        "description": "Стихийный урон: +5%"
      },
      {
        "id": "7-1-3",
        "x": 0.32789603960396047,
        "y": 0.39154613466334165,
        "name": "Стихийный урон: +15%",
        "effect": "Elemental Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "7-1-2",
        "links": [
          "7-1-2",
          "7-1-4"
        ],
        "root": false,
        "description": "Стихийный урон: +15%"
      },
      {
        "id": "7-1-4",
        "x": 0.25091584158415847,
        "y": 0.3281546134663342,
        "name": "Стихийный урон: +5%",
        "effect": "Elemental Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-1-3",
        "links": [
          "7-1-3",
          "7-1-5"
        ],
        "root": false,
        "description": "Стихийный урон: +5%"
      },
      {
        "id": "7-1-5",
        "x": 0.16094059405940597,
        "y": 0.25229426433915214,
        "name": "Стихийный урон: +5%(усиление)",
        "effect": "Elemental Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-1-4",
        "links": [
          "7-1-4"
        ],
        "root": false,
        "description": "Стихийный урон: +5%(усиление)"
      },
      {
        "id": "7-1-6",
        "x": 0.4036386138613861,
        "y": 0.44745635910224435,
        "name": "Физический урон: +5%",
        "effect": "Physical Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-1-1",
        "links": [
          "7-1-1",
          "7-1-7"
        ],
        "root": false,
        "description": "Физический урон: +5%"
      },
      {
        "id": "7-1-7",
        "x": 0.2752970297029703,
        "y": 0.4838154613466334,
        "name": "Физический урон: +15%",
        "effect": "Physical Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "7-1-6",
        "links": [
          "7-1-6",
          "7-1-8"
        ],
        "root": false,
        "description": "Физический урон: +15%"
      },
      {
        "id": "7-1-8",
        "x": 0.3158910891089109,
        "y": 0.5575810473815461,
        "name": "Физический урон: +5%",
        "effect": "Physical Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-1-7",
        "links": [
          "7-1-7",
          "7-1-9"
        ],
        "root": false,
        "description": "Физический урон: +5%"
      },
      {
        "id": "7-1-9",
        "x": 0.14485148514851487,
        "y": 0.541571072319202,
        "name": "Физический урон: +5%(усиление)",
        "effect": "Physical Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-1-8",
        "links": [
          "7-1-8"
        ],
        "root": false,
        "description": "Физический урон: +5%(усиление)"
      },
      {
        "id": "7-1-10",
        "x": 0.5137871287128712,
        "y": 0.34022443890274306,
        "name": "Урон от удара: +5%",
        "effect": "Strike Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-1-1",
        "links": [
          "7-1-1",
          "7-1-11"
        ],
        "root": false,
        "description": "Урон от удара: +5%"
      },
      {
        "id": "7-1-11",
        "x": 0.5939851485148514,
        "y": 0.44640897755610964,
        "name": "Урон от удара: +15%",
        "effect": "Strike Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "7-1-10",
        "links": [
          "7-1-10",
          "7-1-12",
          "7-1-14",
          "7-1-16"
        ],
        "root": false,
        "description": "Урон от удара: +15%"
      },
      {
        "id": "7-1-12",
        "x": 0.6073514851485147,
        "y": 0.31568578553615956,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-1-11",
        "links": [
          "7-1-11",
          "7-1-13"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-1-13",
        "x": 0.683217821782178,
        "y": 0.34206982543640896,
        "name": "Урон от удара: +5%",
        "effect": "Strike Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-1-12",
        "links": [
          "7-1-12"
        ],
        "root": false,
        "description": "Урон от удара: +5%"
      },
      {
        "id": "7-1-14",
        "x": 0.7174999999999999,
        "y": 0.49648379052369074,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-1-11",
        "links": [
          "7-1-11",
          "7-1-15"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-1-15",
        "x": 0.6590841584158414,
        "y": 0.5939401496259351,
        "name": "Урон от удара: +20%",
        "effect": "Strike Damage Increase",
        "value": 20.0,
        "type": "node",
        "parent_id": "7-1-14",
        "links": [
          "7-1-14"
        ],
        "root": false,
        "description": "Урон от удара: +20%"
      },
      {
        "id": "7-1-16",
        "x": 0.5720792079207919,
        "y": 0.5899999999999997,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-1-11",
        "links": [
          "7-1-11",
          "7-1-17"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-1-17",
        "x": 0.4752970297029701,
        "y": 0.5852119700748127,
        "name": "Урон от удара: -8%(усиление)",
        "effect": "Strike Damage Amplification",
        "value": -8.0,
        "type": "node",
        "parent_id": "7-1-16",
        "links": [
          "7-1-16"
        ],
        "root": false,
        "description": "Урон от удара: -8%(усиление)"
      }
    ],
    "2": [
      {
        "id": "7-2-1",
        "x": 0.2988861386138614,
        "y": 0.4002493765586035,
        "name": "Урон: +10%",
        "effect": "Generic Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "7-2-2",
          "7-2-6",
          "7-2-10",
          "7-2-14"
        ],
        "root": true,
        "description": "Урон: +10%"
      },
      {
        "id": "7-2-2",
        "x": 0.4056930693069306,
        "y": 0.2495760598503741,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-2-1",
        "links": [
          "7-2-1",
          "7-2-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-2-3",
        "x": 0.5409653465346533,
        "y": 0.24977556109725685,
        "name": "Критический УРН: +15%",
        "effect": "Critical Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "7-2-2",
        "links": [
          "7-2-2",
          "7-2-4"
        ],
        "root": false,
        "description": "Критический УРН: +15%"
      },
      {
        "id": "7-2-4",
        "x": 0.6613861386138612,
        "y": 0.2549625935162095,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-2-3",
        "links": [
          "7-2-3",
          "7-2-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-2-5",
        "x": 0.7749999999999998,
        "y": 0.2539152119700748,
        "name": "Урон: +5%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-2-4",
        "links": [
          "7-2-4"
        ],
        "root": false,
        "description": "Урон: +5%(усиление)"
      },
      {
        "id": "7-2-6",
        "x": 0.3809405940594059,
        "y": 0.34184538653366586,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-2-1",
        "links": [
          "7-2-1",
          "7-2-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-2-7",
        "x": 0.48898514851485153,
        "y": 0.33206982543640906,
        "name": "Критический УРН: +15%",
        "effect": "Critical Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "7-2-6",
        "links": [
          "7-2-6",
          "7-2-8"
        ],
        "root": false,
        "description": "Критический УРН: +15%"
      },
      {
        "id": "7-2-8",
        "x": 0.6087871287128713,
        "y": 0.3484788029925188,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-2-7",
        "links": [
          "7-2-7",
          "7-2-9"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-2-9",
        "x": 0.7125,
        "y": 0.32498753117206997,
        "name": "Урон: +5%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-2-8",
        "links": [
          "7-2-8"
        ],
        "root": false,
        "description": "Урон: +5%(усиление)"
      },
      {
        "id": "7-2-10",
        "x": 0.40631188118811873,
        "y": 0.44783042394014966,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-2-1",
        "links": [
          "7-2-1",
          "7-2-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-2-11",
        "x": 0.507549504950495,
        "y": 0.4417955112219452,
        "name": "Критический УРН: +15%",
        "effect": "Critical Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "7-2-10",
        "links": [
          "7-2-10",
          "7-2-12"
        ],
        "root": false,
        "description": "Критический УРН: +15%"
      },
      {
        "id": "7-2-12",
        "x": 0.6360148514851485,
        "y": 0.46443890274314226,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-2-11",
        "links": [
          "7-2-11",
          "7-2-13"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-2-13",
        "x": 0.7533415841584158,
        "y": 0.41975062344139663,
        "name": "Урон: +5%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-2-12",
        "links": [
          "7-2-12"
        ],
        "root": false,
        "description": "Урон: +5%(усиление)"
      },
      {
        "id": "7-2-14",
        "x": 0.3493811881188118,
        "y": 0.5176558603491273,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-2-1",
        "links": [
          "7-2-1",
          "7-2-15"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-2-15",
        "x": 0.46299504950495046,
        "y": 0.5265835411471322,
        "name": "Критический УРН: +15%",
        "effect": "Critical Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "7-2-14",
        "links": [
          "7-2-14",
          "7-2-16"
        ],
        "root": false,
        "description": "Критический УРН: +15%"
      },
      {
        "id": "7-2-16",
        "x": 0.6824257425742574,
        "y": 0.556708229426434,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-2-15",
        "links": [
          "7-2-15",
          "7-2-17"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-2-17",
        "x": 0.7805693069306929,
        "y": 0.5332169576059852,
        "name": "Урон: +3%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 3.0,
        "type": "node",
        "parent_id": "7-2-16",
        "links": [
          "7-2-16"
        ],
        "root": false,
        "description": "Урон: +3%(усиление)"
      }
    ],
    "3": [
      {
        "id": "7-3-1",
        "x": 0.4993811881188118,
        "y": 0.37032418952618457,
        "name": "Урон: +15%",
        "effect": "Generic Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "7-3-2",
          "7-3-6",
          "7-3-10",
          "7-3-14",
          "7-3-18",
          "7-3-22",
          "7-3-26",
          "7-3-30"
        ],
        "root": true,
        "description": "Урон: +15%"
      },
      {
        "id": "7-3-2",
        "x": 0.43230198019801974,
        "y": 0.20219451371571068,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-1",
        "links": [
          "7-3-1",
          "7-3-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-3",
        "x": 0.320049504950495,
        "y": 0.19990024937655856,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-2",
        "links": [
          "7-3-2",
          "7-3-4"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-4",
        "x": 0.22883663366336623,
        "y": 0.2013466334164588,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-3",
        "links": [
          "7-3-3",
          "7-3-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-5",
        "x": 0.13700495049504943,
        "y": 0.1628927680798005,
        "name": "Урон: +3%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 3.0,
        "type": "node",
        "parent_id": "7-3-4",
        "links": [
          "7-3-4"
        ],
        "root": false,
        "description": "Урон: +3%(усиление)"
      },
      {
        "id": "7-3-6",
        "x": 0.4143564356435643,
        "y": 0.29945137157107227,
        "name": "Урон: +5%",
        "effect": "Generic Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-3-1",
        "links": [
          "7-3-1",
          "7-3-7"
        ],
        "root": false,
        "description": "Урон: +5%"
      },
      {
        "id": "7-3-7",
        "x": 0.31633663366336623,
        "y": 0.29840399002493767,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-6",
        "links": [
          "7-3-6",
          "7-3-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-8",
        "x": 0.21584158415841576,
        "y": 0.29860349127182045,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-7",
        "links": [
          "7-3-7",
          "7-3-9"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-9",
        "x": 0.13638613861386134,
        "y": 0.27261845386533673,
        "name": "Урон: +5%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-3-8",
        "links": [
          "7-3-8"
        ],
        "root": false,
        "description": "Урон: +5%(усиление)"
      },
      {
        "id": "7-3-10",
        "x": 0.4248762376237623,
        "y": 0.4266334164588529,
        "name": "Урон: +5%",
        "effect": "Generic Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-3-1",
        "links": [
          "7-3-1",
          "7-3-11"
        ],
        "root": false,
        "description": "Урон: +5%"
      },
      {
        "id": "7-3-11",
        "x": 0.3181930693069306,
        "y": 0.42932668329177054,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-10",
        "links": [
          "7-3-10",
          "7-3-12"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-12",
        "x": 0.2313118811881187,
        "y": 0.4045885286783042,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-11",
        "links": [
          "7-3-11",
          "7-3-13"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-13",
        "x": 0.14504950495049496,
        "y": 0.40603491271820447,
        "name": "Урон: +5%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-3-12",
        "links": [
          "7-3-12"
        ],
        "root": false,
        "description": "Урон: +5%(усиление)"
      },
      {
        "id": "7-3-14",
        "x": 0.44529702970297025,
        "y": 0.5263840399002494,
        "name": "Урон: +5%",
        "effect": "Generic Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-3-1",
        "links": [
          "7-3-1",
          "7-3-15"
        ],
        "root": false,
        "description": "Урон: +5%"
      },
      {
        "id": "7-3-15",
        "x": 0.32438118811881184,
        "y": 0.5253366583541147,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-14",
        "links": [
          "7-3-14",
          "7-3-16"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-16",
        "x": 0.23069306930693068,
        "y": 0.5280299251870324,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-15",
        "links": [
          "7-3-15",
          "7-3-17"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-17",
        "x": 0.14628712871287128,
        "y": 0.5107730673316707,
        "name": "Урон: +3%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 3.0,
        "type": "node",
        "parent_id": "7-3-16",
        "links": [
          "7-3-16"
        ],
        "root": false,
        "description": "Урон: +3%(усиление)"
      },
      {
        "id": "7-3-18",
        "x": 0.543069306930693,
        "y": 0.20219451371571076,
        "name": "Урон: +5%",
        "effect": "Generic Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-3-1",
        "links": [
          "7-3-1",
          "7-3-19"
        ],
        "root": false,
        "description": "Урон: +5%"
      },
      {
        "id": "7-3-19",
        "x": 0.6548267326732672,
        "y": 0.21112219451371575,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-18",
        "links": [
          "7-3-18",
          "7-3-20"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-20",
        "x": 0.7517326732673265,
        "y": 0.21755610972568581,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-19",
        "links": [
          "7-3-19",
          "7-3-21"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-21",
        "x": 0.8418316831683166,
        "y": 0.1865835411471322,
        "name": "Урон: +3%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 3.0,
        "type": "node",
        "parent_id": "7-3-20",
        "links": [
          "7-3-20"
        ],
        "root": false,
        "description": "Урон: +3%(усиление)"
      },
      {
        "id": "7-3-22",
        "x": 0.564108910891089,
        "y": 0.31067331670822945,
        "name": "Урон: +5%",
        "effect": "Generic Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-3-1",
        "links": [
          "7-3-1",
          "7-3-23"
        ],
        "root": false,
        "description": "Урон: +5%"
      },
      {
        "id": "7-3-23",
        "x": 0.6517326732673266,
        "y": 0.3033915211970075,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-22",
        "links": [
          "7-3-22",
          "7-3-24"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-24",
        "x": 0.7529702970297028,
        "y": 0.311072319201995,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-23",
        "links": [
          "7-3-23",
          "7-3-25"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-25",
        "x": 0.8424504950495048,
        "y": 0.30254364089775565,
        "name": "Урон: +5%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-3-24",
        "links": [
          "7-3-24"
        ],
        "root": false,
        "description": "Урон: +5%(усиление)"
      },
      {
        "id": "7-3-26",
        "x": 0.5832920792079207,
        "y": 0.43162094763092274,
        "name": "Урон: +5%",
        "effect": "Generic Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-3-1",
        "links": [
          "7-3-1",
          "7-3-27"
        ],
        "root": false,
        "description": "Урон: +5%"
      },
      {
        "id": "7-3-27",
        "x": 0.6758663366336632,
        "y": 0.41810473815461346,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-26",
        "links": [
          "7-3-26",
          "7-3-28"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-28",
        "x": 0.7684405940594058,
        "y": 0.439501246882793,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-27",
        "links": [
          "7-3-27",
          "7-3-29"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-29",
        "x": 0.8603960396039602,
        "y": 0.3948129675810474,
        "name": "Урон: +5%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-3-28",
        "links": [
          "7-3-28"
        ],
        "root": false,
        "description": "Урон: +5%(усиление)"
      },
      {
        "id": "7-3-30",
        "x": 0.5449257425742574,
        "y": 0.5126683291770574,
        "name": "Урон: +5%",
        "effect": "Generic Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-3-1",
        "links": [
          "7-3-1",
          "7-3-31"
        ],
        "root": false,
        "description": "Урон: +5%"
      },
      {
        "id": "7-3-31",
        "x": 0.6511138613861387,
        "y": 0.5253366583541147,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-30",
        "links": [
          "7-3-30",
          "7-3-32"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-32",
        "x": 0.7956683168316833,
        "y": 0.52428927680798,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-3-31",
        "links": [
          "7-3-31",
          "7-3-33"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-3-33",
        "x": 0.8801980198019802,
        "y": 0.49082294264339144,
        "name": "Урон: +3%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 3.0,
        "type": "node",
        "parent_id": "7-3-32",
        "links": [
          "7-3-32"
        ],
        "root": false,
        "description": "Урон: +3%(усиление)"
      }
    ],
    "4": [
      {
        "id": "7-4-1",
        "x": 0.5198019801980198,
        "y": 0.37531172069825436,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": null,
        "links": [
          "7-4-2",
          "7-4-8",
          "7-4-14"
        ],
        "root": true,
        "description": ""
      },
      {
        "id": "7-4-2",
        "x": 0.48242574257425735,
        "y": 0.2844887780548628,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-4-1",
        "links": [
          "7-4-1",
          "7-4-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-4-3",
        "x": 0.3955445544554455,
        "y": 0.26224438902743136,
        "name": "Урон в ближнем бою: +15%",
        "effect": "Melee Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "7-4-2",
        "links": [
          "7-4-2",
          "7-4-4",
          "7-4-6"
        ],
        "root": false,
        "description": "Урон в ближнем бою: +15%"
      },
      {
        "id": "7-4-4",
        "x": 0.2938118811881188,
        "y": 0.26618453865336655,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-4-3",
        "links": [
          "7-4-3",
          "7-4-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-4-5",
        "x": 0.20816831683168316,
        "y": 0.23645885286783042,
        "name": "Урон в ближнем бою: +5%(усиление)",
        "effect": "Melee Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-4-4",
        "links": [
          "7-4-4"
        ],
        "root": false,
        "description": "Урон в ближнем бою: +5%(усиление)"
      },
      {
        "id": "7-4-6",
        "x": 0.3340346534653465,
        "y": 0.36344139650872814,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-4-3",
        "links": [
          "7-4-3",
          "7-4-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-4-7",
        "x": 0.2589108910891089,
        "y": 0.3948129675810474,
        "name": "Урон от удара: -8%(усиление)",
        "effect": "Strike Damage Amplification",
        "value": -8.0,
        "type": "node",
        "parent_id": "7-4-6",
        "links": [
          "7-4-6"
        ],
        "root": false,
        "description": "Урон от удара: -8%(усиление)"
      },
      {
        "id": "7-4-8",
        "x": 0.45767326732673264,
        "y": 0.4303740648379052,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-4-1",
        "links": [
          "7-4-1",
          "7-4-9"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-4-9",
        "x": 0.40297029702970294,
        "y": 0.5116209476309226,
        "name": "Урон по области: +15%",
        "effect": "Area Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "7-4-8",
        "links": [
          "7-4-8",
          "7-4-10",
          "7-4-12"
        ],
        "root": false,
        "description": "Урон по области: +15%"
      },
      {
        "id": "7-4-10",
        "x": 0.3185643564356435,
        "y": 0.5118204488778053,
        "name": "Урон по области: +5%",
        "effect": "Area Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-4-9",
        "links": [
          "7-4-9",
          "7-4-11"
        ],
        "root": false,
        "description": "Урон по области: +5%"
      },
      {
        "id": "7-4-11",
        "x": 0.2186881188118811,
        "y": 0.5232418952618452,
        "name": "Урон по области: +5%(усиление)",
        "effect": "Area Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-4-10",
        "links": [
          "7-4-10"
        ],
        "root": false,
        "description": "Урон по области: +5%(усиление)"
      },
      {
        "id": "7-4-12",
        "x": 0.4936881188118812,
        "y": 0.5130673316708229,
        "name": "Урон по области: +5%",
        "effect": "Area Damage Increase",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-4-9",
        "links": [
          "7-4-9",
          "7-4-13"
        ],
        "root": false,
        "description": "Урон по области: +5%"
      },
      {
        "id": "7-4-13",
        "x": 0.5652227722772276,
        "y": 0.5431920199501246,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-4-12",
        "links": [
          "7-4-12"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-4-14",
        "x": 0.5925742574257425,
        "y": 0.3443391521197008,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-4-1",
        "links": [
          "7-4-1",
          "7-4-15"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-4-15",
        "x": 0.6616336633663366,
        "y": 0.26349127182044896,
        "name": "Урон снаряда: +15%",
        "effect": "Projectile Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "7-4-14",
        "links": [
          "7-4-14",
          "7-4-16",
          "7-4-18"
        ],
        "root": false,
        "description": "Урон снаряда: +15%"
      },
      {
        "id": "7-4-16",
        "x": 0.7319306930693068,
        "y": 0.34099750623441405,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-4-15",
        "links": [
          "7-4-15",
          "7-4-17"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-4-17",
        "x": 0.7855198019801979,
        "y": 0.26264339152119714,
        "name": "Урон снаряда: +30%",
        "effect": "Projectile Damage Increase",
        "value": 30.0,
        "type": "node",
        "parent_id": "7-4-16",
        "links": [
          "7-4-16"
        ],
        "root": false,
        "description": "Урон снаряда: +30%"
      },
      {
        "id": "7-4-18",
        "x": 0.6737623762376236,
        "y": 0.441995012468828,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-4-15",
        "links": [
          "7-4-15",
          "7-4-19"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-4-19",
        "x": 0.750247524752475,
        "y": 0.5145137157107232,
        "name": "Урон снаряда: +5%(усиление)",
        "effect": "Projectile Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-4-18",
        "links": [
          "7-4-18"
        ],
        "root": false,
        "description": "Урон снаряда: +5%(усиление)"
      }
    ],
    "5": [
      {
        "id": "7-5-1",
        "x": 0.23143564356435645,
        "y": 0.2231920199501247,
        "name": "Физический урон: +10%",
        "effect": "Physical Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "7-5-3"
        ],
        "root": true,
        "description": "Физический урон: +10%"
      },
      {
        "id": "7-5-2",
        "x": 0.6472772277227723,
        "y": 0.5049875311720698,
        "name": "Урон холодом: +10%",
        "effect": "Cold Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "7-5-9"
        ],
        "root": true,
        "description": "Урон холодом: +10%"
      },
      {
        "id": "7-5-3",
        "x": 0.19715346534653466,
        "y": 0.3493266832917705,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-5-1",
        "links": [
          "7-5-1",
          "7-5-4"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-5-4",
        "x": 0.1573019801980198,
        "y": 0.4954114713216958,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-5-3",
        "links": [
          "7-5-3",
          "7-5-5",
          "7-5-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-5-5",
        "x": 0.27834158415841587,
        "y": 0.5043391521197008,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-5-4",
        "links": [
          "7-5-4",
          "7-5-6"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-5-6",
        "x": 0.38886138613861393,
        "y": 0.5057855361596011,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-5-5",
        "links": [
          "7-5-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-5-7",
        "x": 0.29566831683168315,
        "y": 0.3933665835411472,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-5-4",
        "links": [
          "7-5-4",
          "7-5-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-5-8",
        "x": 0.3282178217821782,
        "y": 0.24269326683291775,
        "name": "Физический урон: +30%",
        "effect": "Physical Damage Increase",
        "value": 30.0,
        "type": "node",
        "parent_id": "7-5-7",
        "links": [
          "7-5-7"
        ],
        "root": false,
        "description": "Физический урон: +30%"
      },
      {
        "id": "7-5-9",
        "x": 0.532549504950495,
        "y": 0.4478304239401496,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-5-2",
        "links": [
          "7-5-2",
          "7-5-10"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-5-10",
        "x": 0.4506188118811881,
        "y": 0.33581047381546125,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-5-9",
        "links": [
          "7-5-9",
          "7-5-11",
          "7-5-13"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-5-11",
        "x": 0.5073019801980198,
        "y": 0.21506234413965084,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-5-10",
        "links": [
          "7-5-10",
          "7-5-12"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-5-12",
        "x": 0.603589108910891,
        "y": 0.1791022443890274,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-5-11",
        "links": [
          "7-5-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-5-13",
        "x": 0.5499999999999999,
        "y": 0.3123192019950124,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-5-10",
        "links": [
          "7-5-10",
          "7-5-14"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-5-14",
        "x": 0.6376237623762375,
        "y": 0.3511720698254363,
        "name": "Урон холодом: +30%",
        "effect": "Cold Damage Increase",
        "value": 30.0,
        "type": "node",
        "parent_id": "7-5-13",
        "links": [
          "7-5-13"
        ],
        "root": false,
        "description": "Урон холодом: +30%"
      },
      {
        "id": "7-5-15",
        "x": 0.9226485148514851,
        "y": 0.26433915211970077,
        "name": "Урон молнией: +10%",
        "effect": "Lightning Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "7-5-16"
        ],
        "root": true,
        "description": "Урон молнией: +10%"
      },
      {
        "id": "7-5-16",
        "x": 0.9228712871287128,
        "y": 0.4291271820448878,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-5-15",
        "links": [
          "7-5-15",
          "7-5-17"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-5-17",
        "x": 0.8331435643564356,
        "y": 0.49790523690773075,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-5-16",
        "links": [
          "7-5-16",
          "7-5-18",
          "7-5-20"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-5-18",
        "x": 0.7877227722772276,
        "y": 0.34972568578553626,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-5-17",
        "links": [
          "7-5-17",
          "7-5-19"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-5-19",
        "x": 0.7726237623762376,
        "y": 0.18408977556109737,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-5-18",
        "links": [
          "7-5-18"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-5-20",
        "x": 0.8526980198019801,
        "y": 0.37216957605985046,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-5-17",
        "links": [
          "7-5-17",
          "7-5-21"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-5-21",
        "x": 0.8468811881188119,
        "y": 0.22773067331670835,
        "name": "Урон молнией: +30%",
        "effect": "Lightning Damage Increase",
        "value": 30.0,
        "type": "node",
        "parent_id": "7-5-20",
        "links": [
          "7-5-20"
        ],
        "root": false,
        "description": "Урон молнией: +30%"
      }
    ],
    "6": [
      {
        "id": "7-6-1",
        "x": 0.29826732673267325,
        "y": 0.30174563591022446,
        "name": "Урон: +2%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 2.0,
        "type": "node",
        "parent_id": null,
        "links": [],
        "root": true,
        "description": "Урон: +2%(усиление)"
      },
      {
        "id": "7-6-2",
        "x": 0.6497524752475248,
        "y": 0.23690773067331672,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": null,
        "links": [
          "7-6-3"
        ],
        "root": true,
        "description": ""
      },
      {
        "id": "7-6-3",
        "x": 0.6080445544554455,
        "y": 0.3543142144638404,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-6-2",
        "links": [
          "7-6-2",
          "7-6-4",
          "7-6-9"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-6-4",
        "x": 0.5025990099009899,
        "y": 0.36074812967581055,
        "name": "Урон: +5%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-6-3",
        "links": [
          "7-6-3",
          "7-6-5"
        ],
        "root": false,
        "description": "Урон: +5%(усиление)"
      },
      {
        "id": "7-6-5",
        "x": 0.4528465346534652,
        "y": 0.23750623441396518,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-6-4",
        "links": [
          "7-6-4",
          "7-6-6",
          "7-6-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-6-6",
        "x": 0.3566831683168316,
        "y": 0.18159600997506242,
        "name": "",
        "effect": "No parameter",
        "value": 0.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "7-6-5"
        ],
        "root": true,
        "description": ""
      },
      {
        "id": "7-6-7",
        "x": 0.37524752475247514,
        "y": 0.34618453865336674,
        "name": "Урон: +5%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-6-5",
        "links": [
          "7-6-5",
          "7-6-8"
        ],
        "root": false,
        "description": "Урон: +5%(усиление)"
      },
      {
        "id": "7-6-8",
        "x": 0.4548267326732672,
        "y": 0.4473815461346635,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "7-6-7",
        "links": [
          "7-6-7",
          "7-6-9",
          "7-6-10"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "7-6-9",
        "x": 0.6662128712871287,
        "y": 0.4488279301745637,
        "name": "Урон: +5%(усиление)",
        "effect": "Generic Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "7-6-8",
        "links": [
          "7-6-8",
          "7-6-3"
        ],
        "root": false,
        "description": "Урон: +5%(усиление)"
      },
      {
        "id": "7-6-10",
        "x": 0.32772277227722757,
        "y": 0.4513216957605986,
        "name": "",
        "effect": "No parameter",
        "value": 0.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "7-6-8"
        ],
        "root": true,
        "description": ""
      }
    ]
  },
  "8": {
    "1": [
      {
        "id": "8-1-1",
        "x": 0.1998762376237624,
        "y": 0.4027431421446384,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": null,
        "links": [
          "8-1-2",
          "8-1-6",
          "8-1-9"
        ],
        "root": true,
        "description": ""
      },
      {
        "id": "8-1-2",
        "x": 0.24851485148514849,
        "y": 0.2770074812967581,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-1",
        "links": [
          "8-1-1",
          "8-1-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-1-3",
        "x": 0.3522277227722772,
        "y": 0.30837905236907737,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-2",
        "links": [
          "8-1-2",
          "8-1-4"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-1-4",
        "x": 0.44727722772277223,
        "y": 0.3073316708229427,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-3",
        "links": [
          "8-1-3",
          "8-1-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-1-5",
        "x": 0.5596534653465346,
        "y": 0.40977556109725694,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-4",
        "links": [
          "8-1-4",
          "8-1-8",
          "8-1-11",
          "8-1-12",
          "8-1-14",
          "8-1-16"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-1-6",
        "x": 0.29925742574257425,
        "y": 0.43910224438902745,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-1",
        "links": [
          "8-1-1",
          "8-1-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-1-7",
        "x": 0.40111386138613864,
        "y": 0.43805486284289274,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-6",
        "links": [
          "8-1-6",
          "8-1-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-1-8",
        "x": 0.4738861386138614,
        "y": 0.40957605985037404,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-7",
        "links": [
          "8-1-7",
          "8-1-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-1-9",
        "x": 0.3011138613861386,
        "y": 0.5750124688279302,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-1",
        "links": [
          "8-1-1",
          "8-1-10"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-1-10",
        "x": 0.4345297029702971,
        "y": 0.5590024937655861,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-9",
        "links": [
          "8-1-9",
          "8-1-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-1-11",
        "x": 0.5091584158415843,
        "y": 0.5043391521197008,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-10",
        "links": [
          "8-1-10",
          "8-1-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-1-12",
        "x": 0.6268564356435642,
        "y": 0.27032418952618464,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-5",
        "links": [
          "8-1-5",
          "8-1-13"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-1-13",
        "x": 0.715717821782178,
        "y": 0.255561097256858,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-12",
        "links": [
          "8-1-12"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-1-14",
        "x": 0.6559405940594057,
        "y": 0.4099750623441397,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-5",
        "links": [
          "8-1-5",
          "8-1-15"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-1-15",
        "x": 0.7516089108910889,
        "y": 0.4226433915211971,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-14",
        "links": [
          "8-1-14"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-1-16",
        "x": 0.6324257425742573,
        "y": 0.5483790523690774,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-5",
        "links": [
          "8-1-5",
          "8-1-17"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-1-17",
        "x": 0.7169554455445544,
        "y": 0.5124189526184539,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-1-16",
        "links": [
          "8-1-16"
        ],
        "root": false,
        "description": ""
      }
    ],
    "2": [
      {
        "id": "8-2-1",
        "x": 0.1998762376237624,
        "y": 0.6059850374064838,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": null,
        "links": [
          "8-2-2",
          "8-2-12",
          "8-2-15"
        ],
        "root": true,
        "description": ""
      },
      {
        "id": "8-2-2",
        "x": 0.24480198019801977,
        "y": 0.36802992518703237,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-1",
        "links": [
          "8-2-1",
          "8-2-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-2-3",
        "x": 0.3559405940594059,
        "y": 0.38069825436408977,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-2",
        "links": [
          "8-2-2",
          "8-2-4"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-2-4",
        "x": 0.4850247524752475,
        "y": 0.34473815461346635,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-3",
        "links": [
          "8-2-3",
          "8-2-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-2-5",
        "x": 0.5986386138613862,
        "y": 0.40977556109725694,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-4",
        "links": [
          "8-2-4",
          "8-2-6",
          "8-2-8",
          "8-2-10",
          "8-2-14",
          "8-2-17"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-2-6",
        "x": 0.6813118811881188,
        "y": 0.31271820448877813,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-5",
        "links": [
          "8-2-5",
          "8-2-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-2-7",
        "x": 0.7683168316831682,
        "y": 0.35905236907730687,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-6",
        "links": [
          "8-2-6"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-2-8",
        "x": 0.7097772277227723,
        "y": 0.44364089775561105,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-5",
        "links": [
          "8-2-5",
          "8-2-9"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-2-9",
        "x": 0.7707920792079207,
        "y": 0.5336159600997508,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-8",
        "links": [
          "8-2-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-2-10",
        "x": 0.6757425742574258,
        "y": 0.5084788029925188,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-5",
        "links": [
          "8-2-5",
          "8-2-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-2-11",
        "x": 0.7095297029702972,
        "y": 0.6196508728179553,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-10",
        "links": [
          "8-2-10"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-2-12",
        "x": 0.29616336633663365,
        "y": 0.5189027431421446,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-1",
        "links": [
          "8-2-1",
          "8-2-13"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-2-13",
        "x": 0.4209158415841584,
        "y": 0.4991521197007481,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-12",
        "links": [
          "8-2-12",
          "8-2-14"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-2-14",
        "x": 0.5283415841584159,
        "y": 0.48438902743142137,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-13",
        "links": [
          "8-2-13",
          "8-2-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-2-15",
        "x": 0.3073019801980198,
        "y": 0.6485785536159601,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-1",
        "links": [
          "8-2-1",
          "8-2-16"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-2-16",
        "x": 0.4549504950495049,
        "y": 0.6450374064837905,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-15",
        "links": [
          "8-2-15",
          "8-2-17"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-2-17",
        "x": 0.5636138613861386,
        "y": 0.59286783042394,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-2-16",
        "links": [
          "8-2-16",
          "8-2-5"
        ],
        "root": false,
        "description": ""
      }
    ],
    "3": [
      {
        "id": "8-3-1",
        "x": 0.2004950495049505,
        "y": 0.5997506234413965,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": null,
        "links": [
          "8-3-2",
          "8-3-6",
          "8-3-9"
        ],
        "root": true,
        "description": ""
      },
      {
        "id": "8-3-2",
        "x": 0.22438118811881194,
        "y": 0.3992019950124688,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-1",
        "links": [
          "8-3-1",
          "8-3-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-3-3",
        "x": 0.40853960396039607,
        "y": 0.3906733167082294,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-2",
        "links": [
          "8-3-2",
          "8-3-4"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-3-4",
        "x": 0.5264851485148515,
        "y": 0.39586034912718204,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-3",
        "links": [
          "8-3-3",
          "8-3-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-3-5",
        "x": 0.5912128712871287,
        "y": 0.5182543640897757,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-4",
        "links": [
          "8-3-4",
          "8-3-8",
          "8-3-11",
          "8-3-12",
          "8-3-14",
          "8-3-16"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-3-6",
        "x": 0.27821782178217824,
        "y": 0.48024937655860345,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-1",
        "links": [
          "8-3-1",
          "8-3-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-3-7",
        "x": 0.38502475247524764,
        "y": 0.5203491271820448,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-6",
        "links": [
          "8-3-6",
          "8-3-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-3-8",
        "x": 0.4899752475247525,
        "y": 0.508079800498753,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-7",
        "links": [
          "8-3-7",
          "8-3-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-3-9",
        "x": 0.2998762376237624,
        "y": 0.6298753117206982,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-1",
        "links": [
          "8-3-1",
          "8-3-10"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-3-10",
        "x": 0.40977722772277236,
        "y": 0.6749625935162094,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-9",
        "links": [
          "8-3-9",
          "8-3-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-3-11",
        "x": 0.5246287128712872,
        "y": 0.6340149625935161,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-10",
        "links": [
          "8-3-10",
          "8-3-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-3-12",
        "x": 0.6330445544554455,
        "y": 0.39251870324189536,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-5",
        "links": [
          "8-3-5",
          "8-3-13"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-3-13",
        "x": 0.7219059405940593,
        "y": 0.33660847880299266,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-12",
        "links": [
          "8-3-12"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-3-14",
        "x": 0.6881188118811881,
        "y": 0.5221945137157108,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-5",
        "links": [
          "8-3-5",
          "8-3-15"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-3-15",
        "x": 0.7974009900990099,
        "y": 0.5548129675810475,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-14",
        "links": [
          "8-3-14"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-3-16",
        "x": 0.6175742574257426,
        "y": 0.6543640897755612,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-5",
        "links": [
          "8-3-5",
          "8-3-17"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-3-17",
        "x": 0.7243811881188118,
        "y": 0.6857356608478803,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-3-16",
        "links": [
          "8-3-16"
        ],
        "root": false,
        "description": ""
      }
    ],
    "4": [
      {
        "id": "8-4-1",
        "x": 0.20173267326732675,
        "y": 0.5049875311720698,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": null,
        "links": [
          "8-4-2",
          "8-4-6",
          "8-4-9"
        ],
        "root": true,
        "description": ""
      },
      {
        "id": "8-4-2",
        "x": 0.16683168316831687,
        "y": 0.38049875311720693,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-1",
        "links": [
          "8-4-1",
          "8-4-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-4-3",
        "x": 0.3243811881188119,
        "y": 0.3482793017456359,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-2",
        "links": [
          "8-4-2",
          "8-4-4"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-4-4",
        "x": 0.4775990099009901,
        "y": 0.33725685785536164,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-3",
        "links": [
          "8-4-3",
          "8-4-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-4-5",
        "x": 0.5726485148514852,
        "y": 0.5569077306733168,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-4",
        "links": [
          "8-4-4",
          "8-4-8",
          "8-4-11",
          "8-4-12",
          "8-4-14",
          "8-4-16"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-4-6",
        "x": 0.30049504950495054,
        "y": 0.47276807980049873,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-1",
        "links": [
          "8-4-1",
          "8-4-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-4-7",
        "x": 0.39492574257425744,
        "y": 0.5527680798004987,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-6",
        "links": [
          "8-4-6",
          "8-4-8"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-4-8",
        "x": 0.4825495049504951,
        "y": 0.48937655860349116,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-7",
        "links": [
          "8-4-7",
          "8-4-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-4-9",
        "x": 0.1835396039603961,
        "y": 0.6336159600997506,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-1",
        "links": [
          "8-4-1",
          "8-4-10"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-4-10",
        "x": 0.2928217821782179,
        "y": 0.6126184538653365,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-9",
        "links": [
          "8-4-9",
          "8-4-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-4-11",
        "x": 0.4633663366336635,
        "y": 0.6651870324189525,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-10",
        "links": [
          "8-4-10",
          "8-4-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-4-12",
        "x": 0.593440594059406,
        "y": 0.4124688279301746,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-5",
        "links": [
          "8-4-5",
          "8-4-13"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-4-13",
        "x": 0.6866336633663366,
        "y": 0.3503241895261846,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-12",
        "links": [
          "8-4-12"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-4-14",
        "x": 0.6670792079207921,
        "y": 0.5246882793017457,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-5",
        "links": [
          "8-4-5",
          "8-4-15"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-4-15",
        "x": 0.7497524752475249,
        "y": 0.46877805486284285,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-14",
        "links": [
          "8-4-14"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-4-16",
        "x": 0.6547029702970297,
        "y": 0.6456359102244389,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-5",
        "links": [
          "8-4-5",
          "8-4-17"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-4-17",
        "x": 0.7602722772277227,
        "y": 0.6146633416458852,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-4-16",
        "links": [
          "8-4-16"
        ],
        "root": false,
        "description": ""
      }
    ],
    "5": [
      {
        "id": "8-5-1",
        "x": 0.43254950495049505,
        "y": 0.4102244389027431,
        "name": "Физический урон: +10%",
        "effect": "Physical Damage Increase",
        "value": 10.0,
        "type": "node",
        "parent_id": null,
        "links": [
          "8-5-2",
          "8-5-8",
          "8-5-12"
        ],
        "root": true,
        "description": "Физический урон: +10%"
      },
      {
        "id": "8-5-2",
        "x": 0.39207920792079204,
        "y": 0.3194014962593516,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-1",
        "links": [
          "8-5-1",
          "8-5-3"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-5-3",
        "x": 0.3212871287128712,
        "y": 0.30588528678304233,
        "name": "Физический урон: +15%",
        "effect": "Physical Damage Increase",
        "value": 15.0,
        "type": "node",
        "parent_id": "8-5-2",
        "links": [
          "8-5-2",
          "8-5-4",
          "8-5-6"
        ],
        "root": false,
        "description": "Физический урон: +15%"
      },
      {
        "id": "8-5-4",
        "x": 0.24306930693069298,
        "y": 0.4207980049875311,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-3",
        "links": [
          "8-5-3",
          "8-5-5"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-5-5",
        "x": 0.15185643564356427,
        "y": 0.4372069825436409,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-4",
        "links": [
          "8-5-4"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-5-6",
        "x": 0.21955445544554444,
        "y": 0.24748129675810468,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-3",
        "links": [
          "8-5-3",
          "8-5-7"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-5-7",
        "x": 0.12896039603960388,
        "y": 0.2626433915211969,
        "name": "Физический урон: +5%(усиление)",
        "effect": "Physical Damage Amplification",
        "value": 5.0,
        "type": "node",
        "parent_id": "8-5-6",
        "links": [
          "8-5-6"
        ],
        "root": false,
        "description": "Физический урон: +5%(усиление)"
      },
      {
        "id": "8-5-8",
        "x": 0.397029702970297,
        "y": 0.48648379052369073,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-1",
        "links": [
          "8-5-1",
          "8-5-9"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-5-9",
        "x": 0.4116336633663366,
        "y": 0.5951620947630922,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-8",
        "links": [
          "8-5-8",
          "8-5-10",
          "8-5-14"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-5-10",
        "x": 0.32908415841584154,
        "y": 0.6040897755610971,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-9",
        "links": [
          "8-5-9",
          "8-5-11"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-5-11",
        "x": 0.22425742574257423,
        "y": 0.5481795511221944,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-10",
        "links": [
          "8-5-10"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-5-12",
        "x": 0.49542079207920786,
        "y": 0.3605486284289277,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-1",
        "links": [
          "8-5-1",
          "8-5-13"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-5-13",
        "x": 0.5502475247524752,
        "y": 0.2896758104738155,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-12",
        "links": [
          "8-5-12",
          "8-5-16",
          "8-5-18"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-5-14",
        "x": 0.4992574257425743,
        "y": 0.5691770573566084,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-9",
        "links": [
          "8-5-9",
          "8-5-15"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-5-15",
        "x": 0.5844059405940595,
        "y": 0.5768578553615958,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-14",
        "links": [
          "8-5-14"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-5-16",
        "x": 0.6409653465346533,
        "y": 0.34099750623441405,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-13",
        "links": [
          "8-5-13",
          "8-5-17"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-5-17",
        "x": 0.7143564356435641,
        "y": 0.2638902743142146,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-16",
        "links": [
          "8-5-16"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-5-18",
        "x": 0.6372524752475247,
        "y": 0.4133167082294265,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-13",
        "links": [
          "8-5-13",
          "8-5-19"
        ],
        "root": false,
        "description": ""
      },
      {
        "id": "8-5-19",
        "x": 0.7230198019801979,
        "y": 0.45341645885286797,
        "name": "",
        "effect": "No parameter",
        "value": 0,
        "type": "node",
        "parent_id": "8-5-18",
        "links": [
          "8-5-18"
        ],
        "root": false,
        "description": ""
      }
    ]
  },
  "9": {
    "1": []
  }
}''')

    def _node_description(self, effect, value):
        """Build the user-facing node label from its parameter and value."""
        effect = effect or 'No parameter'
        try:
            v = float(value or 0)
        except (TypeError, ValueError):
            v = 0.0
        labels = {
            'Attack Damage Increase': 'Урон при атаке',
            'Attack Damage Amplification': 'Повышает УРН при атаке',
            'Spell Damage Increase': 'Урон при использовании заклинания',
            'Spell Damage Amplification': 'Повышает УРН при использовании заклинания',
            'Physical Damage Increase': 'Физический урон',
            'Physical Damage Amplification': 'Физический урон (усиление)',
            'Fire Damage Increase': 'Огненный урон',
            'Fire Damage Amplification': 'Огненный урон (усиление)',
            'Cold Damage Increase': 'Урон холодом',
            'Cold Damage Amplification': 'Урон холодом (усиление)',
            'Lightning Damage Increase': 'Урон молнией',
            'Lightning Damage Amplification': 'Урон молнией (усиление)',
            'Poison Damage Increase': 'Урон ядом',
            'Poison Damage Amplification': 'Урон ядом (усиление)',
            'Elemental Damage Increase': 'Стихийный урон',
            'Elemental Damage Amplification': 'Стихийный урон (усиление)',
            'Projectile Damage Increase': 'Урон снарядами',
            'Projectile Damage Amplification': 'Урон снарядами (усиление)',
            'Melee Damage Increase': 'Урон в ближнем бою',
            'Melee Damage Amplification': 'Урон в ближнем бою (усиление)',
            'Area Damage Increase': 'Урон по области',
            'Area Damage Amplification': 'Урон по области (усиление)',
            'Strike Damage Increase': 'Урон от удара',
            'Strike Damage Amplification': 'Урон от удара (усиление)',
            'Double Maximum Damage Increase': 'Максимальный УРН (Double)',
            'Triple Maximum Damage Increase': 'Максимальный УРН (Triple)',
            'Maximum Damage Increase': 'Максимальный УРН',
            'Critical Damage Increase': 'Критический УРН',
            'Generic Damage Increase': 'Урон',
            'Generic Damage Amplification': 'Урон (усиление)',
            'No parameter': '',
        }
        label = labels.get(effect, effect)
        if not label:
            return ''
        # Display integer values without a trailing .0, matching the JSON labels.
        vs = f'{v:g}'
        if effect == 'Maximum Damage Increase':
            return f'{label}: +{vs}% (Double +{vs}%, Triple +{2*v:g}%)'
        if effect == 'Triple Maximum Damage Increase':
            return f'{label}: +{vs}%'
        suffix = '(усиление)' if effect.endswith('Amplification') and '(усиление)' not in label else ''
        return f'{label}: +{vs}%'

    def _editor_normalize_nodes(self, nodes):
        """Normalize old parent_id-only layouts to the newer bidirectional link model."""
        by_id={n.get('id'):n for n in nodes if n.get('id')}
        for n in nodes:
            # Old files have no explicit root flag; derive it from parent_id.
            n['root']=bool(n.get('root', n.get('parent_id') is None))
            n['description']=self._node_description(n.get('effect','No parameter') or 'No parameter', n.get('value',0))
            n['name']=n['description']
            if n['root']:
                n['parent_id']=None
            links=n.get('links')
            if not isinstance(links,list):
                n['links']=[]
            n['links']=[x for x in n['links'] if x in by_id and x != n.get('id')]
        for n in nodes:
            parent=n.get('parent_id')
            if parent in by_id and parent != n.get('id'):
                if parent not in n['links']: n['links'].append(parent)
                if n.get('id') not in by_id[parent].setdefault('links',[]):
                    by_id[parent]['links'].append(n.get('id'))

    def _editor_current_branches(self):
        return self.editor_nodes[str(self.editor_constellation.get())]

    def _editor_current_nodes(self):
        branches = self._editor_current_branches()
        key = str(self.editor_branch.get())
        if key not in branches:
            if branches:
                self.editor_branch.set(min(int(k) for k in branches))
                key = str(self.editor_branch.get())
            else:
                self._editor_add_branch(silent=True)
                key = str(self.editor_branch.get())
        self._editor_normalize_nodes(branches[key])
        return branches[key]

    def _editor_rebuild_branch_buttons(self):
        for child in self.editor_branch_bar.winfo_children():
            child.destroy()
        self.editor_branch_buttons=[]
        branches=self._editor_current_branches()
        keys=sorted((int(k) for k in branches), key=int)
        if not keys:
            self.editor_branch.set(0)
            return
        if self.editor_branch.get() not in keys:
            self.editor_branch.set(keys[0])
        branch_img=self._editor_asset_image('branch',24)
        for n in keys:
            rb=ttk.Radiobutton(self.editor_branch_bar, text=str(n), value=n,
                               variable=self.editor_branch,
                               command=self._editor_selection_changed,
                               image=branch_img if branch_img else '',
                               compound='left')
            rb.pack(side='left', padx=2)
            if branch_img:
                rb._editor_image=branch_img
            self.editor_branch_buttons.append(rb)

    def _editor_hotkey(self, event):
        """Handle editor-only keyboard shortcuts."""
        try:
            if self.main_notebook.select() != str(self.editor_tab):
                return
        except Exception:
            return

        # Do not steal E/R while the user is entering/editing text or using
        # a combobox.
        widget = event.widget
        if isinstance(widget, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text)):
            return

        key = str(event.keysym).lower()
        if key == 'e':
            self._editor_add_node()
            return 'break'
        if key == 'r':
            self._editor_start_link()
            return 'break'

    def _editor_selected_node(self):
        sid=getattr(self,'editor_selected_id',None)
        if not sid:
            return None
        return next((n for n in self._editor_current_nodes() if n.get('id')==sid),None)

    def _editor_description_preview(self, *args):
        # Keep the visible description synchronized while editing.  Invalid
        #/empty numeric input is shown as 0 until it becomes a valid number.
        try:
            value=float(self.editor_effect_value_var.get().replace(',','.').strip() or 0)
        except (ValueError, AttributeError):
            value=0.0
        effect=self.editor_effect_var.get() or 'No parameter'
        text=self._node_description(effect, value)
        # The actual node name is the generated description.
        if hasattr(self, 'editor_node_name_var'):
            self.editor_node_name_var.set(text)
        if hasattr(self, 'editor_description_var'):
            self.editor_description_var.set(text)

    def _editor_fill_node_fields(self,node):
        if node is None:
            self.editor_node_name_var.set('')
            self.editor_effect_var.set('No parameter')
            self.editor_effect_value_var.set('0')
            self.editor_description_var.set('')
            self.editor_root_var.set(False)
            return
        generated=self._node_description(node.get('effect','No parameter') or 'No parameter', node.get('value',0))
        self.editor_node_name_var.set(generated)
        self.editor_effect_var.set(str(node.get('effect','No parameter') or 'No parameter'))
        self.editor_effect_value_var.set(str(node.get('value',0)))
        self.editor_description_var.set(generated)
        self.editor_root_var.set(bool(node.get('root', node.get('parent_id') is None)))

    def _editor_apply_node_fields(self):
        node=self._editor_selected_node()
        if node is None:
            self.editor_status.config(text='Сначала выбери нод.')
            return
        try:
            value=float(self.editor_effect_value_var.get().replace(',','.').strip() or 0)
        except ValueError:
            self.editor_status.config(text='Значение % должно быть числом.')
            return
        node['effect']=self.editor_effect_var.get() or 'No parameter'
        node['value']=value
        node['description']=self._node_description(node['effect'], value)
        node['name']=node['description']
        self.editor_node_name_var.set(node['name'])
        self.editor_description_var.set(node['description'])

        # Root is an explicit node property. For backwards compatibility the
        # old parent_id field is kept in sync: a root has no parent.
        make_root=bool(self.editor_root_var.get())
        if make_root:
            node['root']=True
            node['parent_id']=None
            status=f"Сохранено: {node['effect']} = {value:g}%. Нод сделан корневым."
        else:
            node['root']=False
            if node.get('parent_id') is None:
                # When removing root status, restore a sensible parent from an
                # existing graph link if possible. This keeps the branch
                # traversable without forcing JSON editing.
                nodes=self._editor_current_nodes()
                by_id={n.get('id'):n for n in nodes}
                linked=[by_id.get(x) for x in (node.get('links',[]) or [])]
                linked=[x for x in linked if x is not None and x.get('id')!=node.get('id')]
                if linked:
                    node['parent_id']=linked[0].get('id')
                    status=f"Сохранено: {node['effect']} = {value:g}%. Корневой статус снят, родитель: {linked[0].get('name','Нод')}."
                else:
                    # No parent means it would still behave as a root in old
                    # JSON/runtime, so refuse the ambiguous state.
                    node['root']=True
                    self.editor_root_var.set(True)
                    status='Нельзя снять корневой статус: у нода нет родителя или связи, из которой можно восстановить родителя.'
                
            else:
                status=f"Сохранено: {node['effect']} = {value:g}%."
        self.editor_node_label.config(text=node['name'])
        self.editor_status.config(text=status)
        self._editor_draw()

    def _editor_selection_changed(self):
        self._editor_rebuild_branch_buttons()
        self.editor_selected_id=None
        self.editor_drag_id=None
        self.editor_node_label.config(text='Нод не выбран')
        self.editor_node_coords.config(text='X: —   Y: —')
        self._editor_fill_node_fields(None)
        c=self.editor_constellation.get()
        b=self.editor_branch.get()
        self.editor_status.config(text=f'Созвездие {chr(0x2160+c-1)}, ветка {b}.')
        self._editor_draw()

    def _editor_add_branch(self, silent=False):
        ckey=str(self.editor_constellation.get())
        branches=self.editor_nodes[ckey]
        nums=[int(k) for k in branches.keys()]
        new_num=max(nums, default=0)+1
        branches[str(new_num)]=[]
        node_id=f'{ckey}-{new_num}-1'
        branches[str(new_num)].append({
            'id':node_id,'x':0.5,'y':0.5,'name':'Нод 1','effect':'No parameter','value':0,'type':'node','parent_id':None,'links':[],'root':True
        })
        self.editor_branch.set(new_num)
        self.editor_selected_id=node_id
        self._editor_rebuild_branch_buttons()
        self.editor_node_label.config(text='Нод 1')
        self.editor_node_coords.config(text='X: 0.5000   Y: 0.5000')
        self._editor_fill_node_fields(branches[str(new_num)][0])
        if not silent:
            self.editor_status.config(text=f'Создана ветка {new_num} с одним нодом.')
        self._editor_draw()

    def _editor_delete_branch(self):
        from tkinter import messagebox
        ckey=str(self.editor_constellation.get())
        branches=self.editor_nodes[ckey]
        if len(branches)<=1:
            messagebox.showinfo('Удаление ветки', 'Нельзя удалить последнюю ветку созвездия.\nДобавь другую ветку перед удалением этой.')
            return
        bkey=str(self.editor_branch.get())
        if bkey not in branches:
            return
        if not messagebox.askyesno('Удалить ветку', f'Удалить ветку {bkey} вместе со всеми её нодами?'):
            return
        del branches[bkey]
        remaining=sorted(int(k) for k in branches)
        self.editor_branch.set(remaining[0])
        self.editor_selected_id=None
        self.editor_drag_id=None
        self._editor_rebuild_branch_buttons()
        self.editor_node_label.config(text='Нод не выбран')
        self.editor_node_coords.config(text='X: —   Y: —')
        self.editor_status.config(text=f'Ветка {bkey} удалена.')
        self._editor_draw()

    def _editor_canvas_point(self,x,y):
        w=max(self.editor_canvas.winfo_width(),1)
        h=max(self.editor_canvas.winfo_height(),1)
        return max(0,min(1,x/w)), max(0,min(1,y/h))

    def _editor_draw(self):
        if not hasattr(self,'editor_canvas'): return
        c=self.editor_canvas
        c.delete('all')
        w=max(c.winfo_width(),900); h=max(c.winfo_height(),620)
        bg=self._editor_asset_image('background', max(w,h))
        if bg:
            c.create_image(w/2,h/2,image=bg,anchor='center')
            c.create_rectangle(0,0,w,h,fill='',outline='')
            c._editor_background_image=bg
        else:
            c.create_rectangle(0,0,w,h,fill='#06131b',outline='')
        for i in range(260):
            x=(i*137+41)%w; y=(i*79+17)%h
            r=1 if i%8 else 2
            c.create_oval(x-r,y-r,x+r,y+r,fill='#29444d',outline='')
        # Grid helps the user align nodes precisely.
        for k in range(1,10):
            x=w*k/10; y=h*k/10
            c.create_line(x,0,x,h,fill='#102832',width=1)
            c.create_line(0,y,w,y,fill='#102832',width=1)
        nodes=self._editor_current_nodes()
        # Draw connections using each node's explicit parent.  A new node
        # created from a selected node inherits that node as its parent, so
        # the graph reflects the actual branch structure instead of list order.
        by_id={n.get('id'):n for n in nodes}
        drawn=set()
        for node in nodes:
            parent=by_id.get(node.get('parent_id'))
            if parent:
                edge=tuple(sorted((parent['id'],node['id'])))
                if edge not in drawn:
                    c.create_line(parent['x']*w,parent['y']*h,node['x']*w,node['y']*h,
                                  fill='#477887',width=2)
                    drawn.add(edge)
            for lid in node.get('links',[]):
                other=by_id.get(lid)
                if other:
                    edge=tuple(sorted((node['id'],other['id'])))
                    if edge not in drawn:
                        c.create_line(node['x']*w,node['y']*h,other['x']*w,other['y']*h,
                                      fill='#7aa7b2',width=2)
                        drawn.add(edge)
        for node in nodes:
            x=node['x']*w; y=node['y']*h
            selected=node['id']==self.editor_selected_id
            node_img=self._editor_asset_image('node',34 if selected else 30)
            if node_img:
                c.create_image(x,y,image=node_img)
                c._editor_node_image=node_img
                if selected:
                    r=19
                    c.create_oval(x-r,y-r,x+r,y+r,outline='#eaffff',width=2)
            else:
                r=13 if selected else 10
                c.create_oval(x-r,y-r,x+r,y+r,fill='#173b46' if not selected else '#9feef8',
                              outline='#6fc5d5' if not selected else '#eaffff',width=2)
                c.create_text(x,y,text='◆',fill='#d2eef2' if not selected else '#08232b',font=('Segoe UI Symbol',9,'bold'))
            label=node.get('name') or self._node_description(node.get('effect','No parameter') or 'No parameter', node.get('value',0))
            c.create_text(x+15,y-13,text=label,anchor='w',fill='#c6d9de',font=('Segoe UI',8))
        c.create_text(10,10,text=f'Созвездие {chr(0x2160+self.editor_constellation.get()-1)} — ветка {self.editor_branch.get()}',
                      anchor='nw',fill='#d7e7ea',font=('Segoe UI',10,'bold'))

    def _editor_find_node(self,x,y):
        w=max(self.editor_canvas.winfo_width(),1); h=max(self.editor_canvas.winfo_height(),1)
        best=None; bestd=18**2
        for node in self._editor_current_nodes():
            nx=node['x']*w; ny=node['y']*h
            d=(x-nx)**2+(y-ny)**2
            if d<bestd:
                best=node; bestd=d
        return best

    def _editor_mouse_down(self,event):
        node=self._editor_find_node(event.x,event.y)
        if not node: return
        if getattr(self,'editor_link_mode',False):
            source_id=self.editor_link_source_id
            target_id=node['id']
            if source_id and source_id != target_id:
                nodes=self._editor_current_nodes()
                by_id={n.get('id'):n for n in nodes}
                src=by_id.get(source_id); dst=by_id.get(target_id)
                if src and dst:
                    src.setdefault('links',[]); dst.setdefault('links',[])
                    if target_id not in src['links']:
                        src['links'].append(target_id)
                        dst['links'].append(source_id)
                        self.editor_status.config(text=f'Связь создана: {src.get("name","Нод")} ↔ {dst.get("name","Нод")}.')
                    else:
                        self.editor_status.config(text='Эти ноды уже связаны.')
            self.editor_link_mode=False
            self.editor_link_source_id=None
            self.editor_selected_id=node['id']
            self._editor_fill_node_fields(node)
            self.editor_node_label.config(text=node.get('name','Нод'))
            self.editor_node_coords.config(text=f"X: {node['x']:.4f}   Y: {node['y']:.4f}")
            self._editor_draw()
            return
        self.editor_selected_id=node['id']
        self.editor_drag_id=node['id']
        w=max(self.editor_canvas.winfo_width(),1); h=max(self.editor_canvas.winfo_height(),1)
        self.editor_drag_offset=(event.x-node['x']*w,event.y-node['y']*h)
        self.editor_node_label.config(text=node['name'])
        self.editor_node_coords.config(text=f"X: {node['x']:.4f}   Y: {node['y']:.4f}")
        self._editor_fill_node_fields(node)
        self.editor_status.config(text='Нод выбран. Перетащи его мышью или измени параметры справа.')
        self._editor_draw()

    def _editor_mouse_drag(self,event):
        if not self.editor_drag_id: return
        w=max(self.editor_canvas.winfo_width(),1); h=max(self.editor_canvas.winfo_height(),1)
        ox,oy=self.editor_drag_offset
        x=max(0,min(w,event.x-ox)); y=max(0,min(h,event.y-oy))
        nx,ny=self._editor_canvas_point(x,y)
        for node in self._editor_current_nodes():
            if node['id']==self.editor_drag_id:
                node['x']=nx; node['y']=ny
                self.editor_node_coords.config(text=f"X: {nx:.4f}   Y: {ny:.4f}")
                break
        self._editor_draw()

    def _editor_mouse_up(self,event):
        self.editor_drag_id=None

    def _editor_add_node(self):
        nodes=self._editor_current_nodes()
        n=len(nodes)+1

        # If a node is selected, the new node is created as its child.  It is
        # placed a short distance down/right from the parent and connected to
        # it immediately.  The user can then drag the child to its exact
        # in-game position.
        parent=None
        if self.editor_selected_id:
            parent=next((x for x in nodes if x.get('id')==self.editor_selected_id),None)

        if parent:
            px,py=float(parent.get('x',0.5)),float(parent.get('y',0.5))
            # Prefer a free direction around the parent.
            candidates=[(0.10,0.08),(-0.10,0.08),(0.10,-0.08),(-0.10,-0.08),
                        (0.0,0.11),(0.0,-0.11),(0.13,0.0),(-0.13,0.0)]
            occupied={(round(float(x.get('x',0.5)),3),round(float(x.get('y',0.5)),3)) for x in nodes}
            x,y=px+0.10,py+0.08
            for dx,dy in candidates:
                tx=max(0.04,min(0.96,px+dx)); ty=max(0.04,min(0.96,py+dy))
                if (round(tx,3),round(ty,3)) not in occupied:
                    x,y=tx,ty
                    break
            parent_id=parent.get('id')
            status=f'Добавлен {"Нод "+str(n)} из {parent.get("name","выбранного нода")}. Перетащи его в нужное место.'
        else:
            x,y=0.5,0.5
            parent_id=None
            status=f'Добавлен Нод {n} в центре. Чтобы создать дочерний нод, сначала кликни по ноду.'

        node={'id':f'{self.editor_constellation.get()}-{self.editor_branch.get()}-{n}',
              'x':x,'y':y,'name':f'Нод {n}','effect':'No parameter','value':0,'type':'node','parent_id':parent_id,'links':[],'root':parent_id is None}
        nodes.append(node)
        self.editor_selected_id=node['id']
        self.editor_status.config(text=status)
        self.editor_node_label.config(text=node['name'])
        self.editor_node_coords.config(text=f'X: {x:.4f}   Y: {y:.4f}')
        self._editor_fill_node_fields(node)
        self._editor_draw()

    def _editor_start_link(self):
        node=self._editor_selected_node()
        if node is None:
            self.editor_status.config(text='Сначала выбери первый нод, затем нажми «↔ Связать» и кликни по второму ноду.')
            return
        self.editor_link_mode=True
        self.editor_link_source_id=node['id']
        self.editor_status.config(text=f'Режим связи: выбран «{node.get("name","Нод")}». Теперь кликни по второму ноду.')
        self._editor_draw()

    def _editor_unlink_selected(self):
        node=self._editor_selected_node()
        if node is None:
            self.editor_status.config(text='Сначала выбери нод.')
            return
        links=list(node.get('links',[]))
        parent=node.get('parent_id')
        if not links and not parent:
            self.editor_status.config(text='У выбранного нода нет дополнительных связей.')
            return
        nodes=self._editor_current_nodes()
        by_id={n.get('id'):n for n in nodes}
        # Remove explicit links from both sides. parent_id is intentionally kept;
        # use «− Нод» or JSON editing if the original tree parent must change.
        for lid in links:
            other=by_id.get(lid)
            if other and isinstance(other.get('links'),list):
                other['links']=[x for x in other['links'] if x!=node.get('id')]
        node['links']=[]
        self.editor_status.config(text='Дополнительные связи выбранного нода удалены.')
        self._editor_draw()

    def _editor_delete_node(self):
        nodes=self._editor_current_nodes()
        selected=self.editor_selected_id
        for n in nodes:
            if isinstance(n.get('links'),list):
                n['links']=[x for x in n['links'] if x!=selected]
            if n.get('parent_id')==selected:
                n['parent_id']=None
        before=len(nodes)
        nodes[:]=[n for n in nodes if n['id']!=self.editor_selected_id]
        if len(nodes)!=before:
            self.editor_status.config(text='Нод удалён.')
        self.editor_selected_id=None
        self.editor_node_label.config(text='Нод не выбран')
        self.editor_node_coords.config(text='X: —   Y: —')
        self._editor_fill_node_fields(None)
        self._editor_draw()

    def _editor_json_payload(self):
        return {
            'format':'undecember_constellation_layout_v1',
            'description':'Editable node positions for the UNDECEMBER Zodiac calculator.',
            'coordinate_system':'normalized_0_to_1',
            'assets': {k: (f'assets/{k}.png' if v else None) for k,v in self.editor_assets.items()},
            'constellations':self.editor_nodes,
        }

    def _editor_json_text(self):
        return json.dumps(self._editor_json_payload(),ensure_ascii=False,indent=2)

    def _editor_save_json(self):
        from tkinter import filedialog
        path=filedialog.asksaveasfilename(title='Сохранить layout JSON',defaultextension='.json',
                                         filetypes=[('JSON','*.json'),('Все файлы','*.*')],
                                         initialfile='constellation_layout.json')
        if not path: return
        Path(path).write_text(self._editor_json_text(),encoding='utf-8')
        self.editor_status.config(text=f'Сохранено:\n{path}')

    def _editor_export_json(self):
        from tkinter import filedialog
        path=filedialog.asksaveasfilename(title='Экспорт для ChatGPT',defaultextension='.json',
                                         filetypes=[('JSON','*.json'),('Все файлы','*.*')],
                                         initialfile='constellation_layout_for_chatgpt.json')
        if not path: return
        Path(path).write_text(self._editor_json_text(),encoding='utf-8')
        try:
            self.clipboard_clear(); self.clipboard_append(self._editor_json_text()); self.update()
            copied='JSON также скопирован в буфер обмена.'
        except tk.TclError:
            copied=''
        self.editor_status.config(text=f'Экспортировано:\n{path}\n{copied}\nПришли мне этот JSON-файл.')

    def _editor_load_json(self):
        from tkinter import filedialog, messagebox
        path=filedialog.askopenfilename(title='Загрузить layout JSON',
                                       filetypes=[('JSON','*.json'),('Все файлы','*.*')])
        if not path: return
        try:
            payload=json.loads(Path(path).read_text(encoding='utf-8'))
            if payload.get('format')!='undecember_constellation_layout_v1':
                raise ValueError('Неизвестный формат layout.')
            consts=payload.get('constellations')
            if not isinstance(consts,dict): raise ValueError('Нет раздела constellations.')
            # Minimal validation: positions must be finite numbers in 0..1.
            for ckey,branches in consts.items():
                int(ckey)
                if not isinstance(branches,dict): raise ValueError('Некорректная ветка.')
                for bkey,nodes in branches.items():
                    int(bkey)
                    if not isinstance(nodes,list): raise ValueError('Некорректный список нодов.')
                    for node in nodes:
                        x=float(node['x']); y=float(node['y'])
                        if not (0<=x<=1 and 0<=y<=1): raise ValueError('Координаты должны быть 0..1.')
                        node.setdefault('name', f"Нод {node.get('id','')}")
                        node.setdefault('effect', 'No parameter')
                        node.setdefault('value', 0)
                        node.setdefault('type', 'node')
                        node.setdefault('parent_id', None)
                        node.setdefault('links', [])
                        node.setdefault('root', node.get('parent_id') is None)
                        float(node.get('value', 0))
            for branches in consts.values():
                for nodes in branches.values():
                    self._editor_normalize_nodes(nodes)
            self.editor_nodes=consts
            self.editor_selected_id=None
            self._editor_draw()
            self.editor_status.config(text=f'Загружено:\n{path}')
        except Exception as exc:
            messagebox.showerror('Ошибка layout JSON',str(exc))

    def section(self, parent, text):
        lf = ttk.LabelFrame(parent, text=text, padding=8)
        lf.pack(fill='x', pady=(0, 8))
        return lf

    def _character(self, p):
        lf = self.section(p, '1. ПАРАМЕТРЫ ПЕРСОНАЖА')
        headers = ['Параметр', 'MIN', 'MAX', 'INCREASE %', 'AMPLIFICATION %']
        for c, h in enumerate(headers):
            ttk.Label(lf, text=h, font=('Segoe UI', 9, 'bold')).grid(row=0, column=c, padx=3)

        # MIN/MAX are only for a damage range. Increase and Amplification are
        # scalar stats, so they have their own columns and are not duplicated
        # between MIN and MAX.
        base_rows = [
            ('Attack base flat', 'atkBaseMin', '0', 'atkBaseMax', '0', 'atkInc', '0', 'atkAmp', '0'),
            ('Spell base flat', 'spellBaseMin', '0', 'spellBaseMax', '0', 'spellInc', '0', 'spellAmp', '0'),
        ]
        for r, (label, a, av, b, bv, inc, incv, amp, ampv) in enumerate(base_rows, 1):
            ttk.Label(lf, text=label, width=28).grid(row=r, column=0, sticky='w')
            self.entry(lf, a, av).grid(row=r, column=1)
            self.entry(lf, b, bv).grid(row=r, column=2)
            self.multi_entry(lf, inc, incv).grid(row=r, column=3)
            self.multi_entry(lf, amp, ampv).grid(row=r, column=4)

        ttk.Label(lf, text='Calculated Attack/Spell Damage', width=28).grid(row=3, column=0, sticky='w')
        self.var('calcAtkMin', '0'); self.var('calcAtkMax', '0')
        self.var('calcSpellMin', '0'); self.var('calcSpellMax', '0')
        ttk.Label(lf, textvariable=self.vars['calcAtkMin']).grid(row=3, column=1)
        ttk.Label(lf, text=' – ').grid(row=3, column=2)
        ttk.Label(lf, textvariable=self.vars['calcAtkMax']).grid(row=3, column=2, padx=(25,0), sticky='w')
        ttk.Label(lf, text='Attack = base × (1 + Increase) × (1 + Amplification)', foreground='#555').grid(row=3, column=3, columnspan=2, sticky='w')
        ttk.Label(lf, text='Calculated Spell Damage', width=28).grid(row=4, column=0, sticky='w')
        ttk.Label(lf, textvariable=self.vars['calcSpellMin']).grid(row=4, column=1)
        ttk.Label(lf, text=' – ').grid(row=4, column=2)
        ttk.Label(lf, textvariable=self.vars['calcSpellMax']).grid(row=4, column=2, padx=(25,0), sticky='w')
        ttk.Label(lf, text='Spell = base × (1 + Increase) × (1 + Amplification)', foreground='#555').grid(row=4, column=3, columnspan=2, sticky='w')

        damage_rows = [
            ('Physical flat (raw)', 'pFlatMin', '0', 'pFlatMax', '0', 'pInc', '0', 'pAmp', '0'),
            ('Fire flat (raw)', 'fFlatMin', '0', 'fFlatMax', '0', 'fInc', '0', 'fAmp', '0'),
            ('Cold flat (raw)', 'cFlatMin', '0', 'cFlatMax', '0', 'cInc', '0', 'cAmp', '0'),
            ('Lightning flat (raw)', 'lFlatMin', '0', 'lFlatMax', '0', 'lInc', '0', 'lAmp', '0'),
            ('Poison flat (raw)', 'oFlatMin', '0', 'oFlatMax', '0', 'oInc', '0', 'oAmp', '0'),
            ('Chaos flat (raw)', 'hFlatMin', '0', 'hFlatMax', '0', 'hInc', '0', 'hAmp', '0'),
        ]
        for r, (label, fmin, fminv, fmax, fmaxv, inc, incv, amp, ampv) in enumerate(damage_rows, 6):
            ttk.Label(lf, text=label, width=28).grid(row=r, column=0, sticky='w')
            self.entry(lf, fmin, fminv).grid(row=r, column=1)
            self.entry(lf, fmax, fmaxv).grid(row=r, column=2)
            self.multi_entry(lf, inc, incv).grid(row=r, column=3)
            self.multi_entry(lf, amp, ampv).grid(row=r, column=4)

        ttk.Label(lf, text='Base Attack/Spell flat сначала преобразуется через свой Increase и Amplification; только рассчитанный результат идёт в tooltip.', foreground='#8a4b00').grid(row=12, column=0, columnspan=5, sticky='w', pady=(5,0))
        ttk.Label(lf, text='Источник').grid(row=13, column=0, sticky='w')
        self.var('source', 'Attack')
        ttk.Combobox(lf, textvariable=self.vars['source'], values=['Attack', 'Spell'], state='readonly', width=11).grid(row=13, column=1, sticky='w')
        ttk.Label(lf, text='% Урон').grid(row=14, column=0, sticky='w')
        self.multi_entry(lf, 'genericInc', '0').grid(row=14, column=1)
        ttk.Label(lf, text='% Урон (усиление)').grid(row=14, column=2, sticky='e')
        self.multi_entry(lf, 'genericAmp', '0').grid(row=14, column=3)
        ttk.Label(lf, text='Global Increase добавляется к каждому типу; Global Amplification — отдельный multiplicative Amp.', foreground='#555').grid(row=15, column=0, columnspan=5, sticky='w')

    def _skill(self, p):
        lf = self.section(p, '2. ПАРАМЕТРЫ НАВЫКА')
        ttk.Label(lf, text='Тип').grid(row=0, column=0)
        ttk.Label(lf, text='Skill Damage %').grid(row=0, column=1)
        ttk.Label(lf, text='flat').grid(row=0, column=2)
        ttk.Label(lf, text='Тултип MIN').grid(row=0, column=3)
        ttk.Label(lf, text='Тултип MAX').grid(row=0, column=4)

        data = [
            ('Physical','pSkill','pSkillFlat','tooltipPMin','tooltipPMax'),
            ('Fire','fSkill','fSkillFlat','tooltipFMin','tooltipFMax'),
            ('Cold','cSkill','cSkillFlat','tooltipCMin','tooltipCMax'),
            ('Lightning','lSkill','lSkillFlat','tooltipLMin','tooltipLMax'),
            ('Poison','oSkill','oSkillFlat','tooltipOMin','tooltipOMax'),
            ('Chaos','hSkill','hSkillFlat','tooltipHMin','tooltipHMax'),
        ]
        for r,(name,skill_key,flat_key,tmin,tmax) in enumerate(data,1):
            ttk.Label(lf,text=name).grid(row=r,column=0,sticky='w')
            self.entry(lf,skill_key,'0').grid(row=r,column=1)
            self.entry(lf,flat_key,'0').grid(row=r,column=2)
            self.entry(lf,tmin,'0').grid(row=r,column=3)
            self.entry(lf,tmax,'0').grid(row=r,column=4)

        ttk.Label(
            lf,
            text='Тултип — это отдельный ввод фактического значения, отображаемого игрой. Он нужен для сравнения с расчётом и не заменяет Skill Damage % и flat.',
            foreground='#555'
        ).grid(row=7, column=0, columnspan=5, sticky='w', pady=(6,0))
        ttk.Label(
            lf,
            text='Если MIN/MAX тултипа заполнены, они заменяют рассчитанный компонент именно на этапе основного тултипа. Все последующие стадии (теги, доп. урон, Double/Triple/Critical) работают поверх введённого тултипа.',
            foreground='#8a4b00'
        ).grid(row=8, column=0, columnspan=5, sticky='w')
    def _tags(self, p):
        lf = self.section(p, '3. ТЕГОВЫЕ МОДИФИКАТОРЫ')
        # K coefficients remain fully active in the calculation, but are hidden
        # from the user interface. They are internal calibration constants.
        heads=['Тег','Increase %','Amplification %']
        for c,h in enumerate(heads): ttk.Label(lf,text=h,font=('Segoe UI',9,'bold')).grid(row=0,column=c,padx=3)
        tags=[('Area','tagArea','areaInc','areaAmp'),('Projectile','tagProj','projInc','projAmp'),('Melee','tagMelee','meleeInc','meleeAmp'),('Strike','tagStrike','strikeInc','strikeAmp')]
        for r,(name,ck,ik,ak) in enumerate(tags,1):
            self.checkbox(lf,ck,name).grid(row=r,column=0,sticky='w')
            self.multi_entry(lf,ik,'0',9).grid(row=r,column=1)
            self.multi_entry(lf,ak,'0',9).grid(row=r,column=2)

    def _special(self,p):
        lf=self.section(p,'4. ДОПОЛНИТЕЛЬНЫЙ УРОН (до 5)')
        for c,h in enumerate(['On','Source','Target','%']): ttk.Label(lf,text=h,font=('Segoe UI',9,'bold')).grid(row=0,column=c)
        for i in range(1,6):
            self.checkbox(lf,f'sp{i}').grid(row=i,column=0)
            self.combo(lf, f'sp{i}src', ['Physical','Cold','Lightning','Poison','Fire'], 'Fire', 11).grid(row=i,column=1)
            self.combo(lf, f'sp{i}dst', ['Physical','Cold','Lightning','Poison','Fire'], 'Cold', 11).grid(row=i,column=2)
            self.entry(lf,f'sp{i}pct','0',8).grid(row=i,column=3)
        ttk.Label(lf,text='Если Source = Target, пакет входит в основной tooltip этой стихии. Иначе показывается отдельно.').grid(row=6,column=0,columnspan=4,sticky='w')

    def _post(self,p):
        lf=self.section(p,'5. ПОСЛЕ ТУЛТИПА')
        fields=[('Double Maximum Damage Increase','doublePct','0'),('Triple Maximum Damage Increase','triplePct','0'),('Critical Damage %','critDmgPct','0'),('Critical Chance %','critChance','0')]
        for r,(name,k,v) in enumerate(fields):
            ttk.Label(lf,text=name).grid(row=r,column=0,sticky='w')
            self.entry(lf,k,v).grid(row=r,column=1)

    def reset(self):
        defaults={'genericInc':'0','genericAmp':'0','atkInc':'0','atkAmp':'0','spellInc':'0','spellAmp':'0','doublePct':'0','triplePct':'0','critDmgPct':'0','critChance':'0','physKMin':'0.80014461','physKMax':'0.84762186','elemKMin':'0.74262000','elemKMax':'0.74262000'}
        for k,v in defaults.items(): self.vars[k].set(v)
        multi_defaults = {
            'genericInc':'0','genericAmp':'0','atkInc':'0','atkAmp':'0','spellInc':'0','spellAmp':'0',
            'pInc':'345','pAmp':'49.6','fInc':'345','fAmp':'28',
            'cInc':'345','cAmp':'28','lInc':'345','lAmp':'28',
            'oInc':'345','oAmp':'28','hInc':'345','hAmp':'28',
            'areaInc':'0','areaAmp':'0','projInc':'0','projAmp':'0','meleeInc':'0','meleeAmp':'0','strikeInc':'0','strikeAmp':'0'
        }
        for k,v in multi_defaults.items():
            if k in self.multi_vars:
                self.reset_multi(k, v)
        self.vars['source'].set('Attack')
        for i in range(1,6):
            self.vars[f'sp{i}src'].set('Fire')
            self.vars[f'sp{i}dst'].set('Cold')
        for k,v in {'atkBaseMin':'0','atkBaseMax':'0','spellBaseMin':'0','spellBaseMax':'0','pFlatMin':'0','pFlatMax':'0','pInc':'0','pAmp':'0','fFlatMin':'0','fFlatMax':'0','fInc':'0','fAmp':'0','cFlatMin':'0','cFlatMax':'0','cInc':'0','cAmp':'0','lFlatMin':'0','lFlatMax':'0','lInc':'0','lAmp':'0','oFlatMin':'0','oFlatMax':'0','oInc':'0','oAmp':'0','hFlatMin':'0','hFlatMax':'0','hInc':'0','hAmp':'0','tooltipPMin':'0','tooltipPMax':'0','tooltipFMin':'0','tooltipFMax':'0','tooltipCMin':'0','tooltipCMax':'0','tooltipLMin':'0','tooltipLMax':'0','tooltipOMin':'0','tooltipOMax':'0','tooltipHMin':'0','tooltipHMax':'0','pSkill':'0','pSkillFlat':'0','fSkill':'0','fSkillFlat':'0','cSkill':'0','cSkillFlat':'0','lSkill':'0','lSkillFlat':'0','oSkill':'0','oSkillFlat':'0','hSkill':'0','hSkillFlat':'0','areaInc':'0','areaAmp':'0','areaKMin':'27.22901910','areaKMax':'26.06424224','projInc':'0','projAmp':'0','projKMin':'27.26937656','projKMax':'26.08843876','meleeInc':'0','meleeAmp':'0','meleeKMin':'27.28406285','meleeKMax':'26.09530493','strikeInc':'0','strikeAmp':'0','strikeKMin':'27.22901910','strikeKMax':'26.06424224','constStrikeInc':'0','constStrikeAmp':'0'}.items(): self.vars[k].set(v)
        constellation_defaults = {
            'constAtkInc':'0','constAtkAmp':'0','constSpellInc':'0','constSpellAmp':'0',
            'constPhysInc':'0','constPhysAmp':'0','constFireInc':'0','constFireAmp':'0',
            'constColdInc':'0','constColdAmp':'0','constPoisonInc':'0','constPoisonAmp':'0',
            'constLightningInc':'0','constLightningAmp':'0',
            'constElemInc':'0','constElemAmp':'0',
            'constAreaInc':'0','constAreaAmp':'0',
            'constProjInc':'0','constProjAmp':'0','constMeleeInc':'0','constMeleeAmp':'0','constStrikeInc':'0','constStrikeAmp':'0',
            'constMaxDmg':'0','constCritDmg':'0','constGenericInc':'0','constGenericAmp':'0'
        }
        for k,v in constellation_defaults.items(): self.vars[k].set(v)
        # Calculator reset must not silently disable the currently selected
        # constellation nodes. Restore their aggregated bonuses afterwards.
        if hasattr(self, 'runtime_active') and hasattr(self, 'runtime_nodes'):
            self._runtime_apply_to_vars()
        for k in self.checks: self.checks[k].set(False)
        self.calculate()

    def component(self,name,flatmin,flatmax,inc_eff,amp_factor,skill,skillflat,kmin,kmax,bmin,bmax):
        # Component receives the COMPLETE effective Increase/Amp pools from
        # calculate(). It performs only the arithmetic for this damage type.
        # Generic/Zodiac modifiers are therefore applied exactly once.
        mn=(bmin+flatmin+skillflat)*(1+inc_eff/100)*amp_factor*(skill/100)*kmin
        mx=(bmax+flatmax+skillflat)*(1+inc_eff/100)*amp_factor*(skill/100)*kmax
        return mn,mx

    def tag_component(self, base_min, base_max, inc_key, amp_key, kmin_key, kmax_key):
        # Tag Increase is a tag-specific additive contribution measured by K.
        # Tag Amplification is handled separately in calculate(): all active
        # tag amplifications act on one common pre-K tag amplification pool.
        inc_total = self.multi_sum(inc_key)
        amp_factor = self.multi_amp_factor(amp_key)
        kmin = f(self.vars[kmin_key].get()) / 100.0
        kmax = f(self.vars[kmax_key].get()) / 100.0
        tag_bonus_min = base_min * kmin * (inc_total / 100.0)
        tag_bonus_max = base_max * kmax * (inc_total / 100.0)
        return tag_bonus_min, tag_bonus_max, inc_total, amp_factor

    def calculate(self):
        source=self.vars['source'].get()
        atk_base_min=f(self.vars['atkBaseMin'].get()); atk_base_max=f(self.vars['atkBaseMax'].get())
        spell_base_min=f(self.vars['spellBaseMin'].get()); spell_base_max=f(self.vars['spellBaseMax'].get())
        atk_factor=(1 + (self.multi_sum('atkInc')+f(self.vars['constAtkInc'].get()))/100.0) * self.multi_amp_factor('atkAmp') * (1+f(self.vars['constAtkAmp'].get())/100.0)
        spell_factor=(1 + (self.multi_sum('spellInc')+f(self.vars['constSpellInc'].get()))/100.0) * self.multi_amp_factor('spellAmp') * (1+f(self.vars['constSpellAmp'].get())/100.0)
        atk_min=atk_base_min*atk_factor; atk_max=atk_base_max*atk_factor
        spell_min=spell_base_min*spell_factor; spell_max=spell_base_max*spell_factor
        self.vars['calcAtkMin'].set(f'{atk_min:,.2f}'); self.vars['calcAtkMax'].set(f'{atk_max:,.2f}')
        self.vars['calcSpellMin'].set(f'{spell_min:,.2f}'); self.vars['calcSpellMax'].set(f'{spell_max:,.2f}')
        bmin, bmax = (atk_min, atk_max) if source=='Attack' else (spell_min, spell_max)
        data=[
            ('Physical','pFlatMin','pFlatMax','pInc','pAmp','pSkill','pSkillFlat','physKMin','physKMax'),
            ('Fire','fFlatMin','fFlatMax','fInc','fAmp','fSkill','fSkillFlat','elemKMin','elemKMax'),
            ('Cold','cFlatMin','cFlatMax','cInc','cAmp','cSkill','cSkillFlat','elemKMin','elemKMax'),
            ('Lightning','lFlatMin','lFlatMax','lInc','lAmp','lSkill','lSkillFlat','elemKMin','elemKMax'),
            ('Poison','oFlatMin','oFlatMax','oInc','oAmp','oSkill','oSkillFlat','elemKMin','elemKMax'),
            ('Chaos','hFlatMin','hFlatMax','hInc','hAmp','hSkill','hSkillFlat','elemKMin','elemKMax')]
        comps={}; lines=[f'=== {APP_TITLE} ===','',f'Источник: {source} | Calculated Base Damage: {fmt(bmin,bmax)}',f'Attack calculated: {fmt(atk_min,atk_max)} | factor {atk_factor:.8f}',f'Spell calculated: {fmt(spell_min,spell_max)} | factor {spell_factor:.8f}','', '1. ОСНОВНОЙ ТУЛТИП']
        direct_min=direct_max=0
        gen_inc=self.multi_sum('genericInc')+f(self.vars['constGenericInc'].get())
        gen_amp=self.multi_amp_factor('genericAmp')*(1+f(self.vars['constGenericAmp'].get())/100.0)
        for name,a,b,inc,amp,skill,skillflat,kmn,kmx in data:
            s=f(self.vars[skill].get())
            # Keep the calculated component available for diagnostics, but when
            # a real in-game tooltip is entered, that tooltip REPLACES the
            # calculated component at this exact stage of the pipeline.
            tmap={
                'Physical':('tooltipPMin','tooltipPMax'),
                'Fire':('tooltipFMin','tooltipFMax'),
                'Cold':('tooltipCMin','tooltipCMax'),
                'Lightning':('tooltipLMin','tooltipLMax'),
                'Poison':('tooltipOMin','tooltipOMax'),
                'Chaos':('tooltipHMin','tooltipHMax'),
            }
            tmin_key,tmax_key=tmap[name]
            entered_tmin=f(self.vars[tmin_key].get())
            entered_tmax=f(self.vars[tmax_key].get())
            has_entered_tooltip=(entered_tmin != 0 or entered_tmax != 0)
            if s==0 and not has_entered_tooltip:
                continue
            # Generic Damage belongs to the same Increase/Amp stage as the
            # component-specific Damage modifiers. It is therefore merged into
            # each component exactly once, rather than multiplied onto the
            # already-summed subtotal as a separate factor.
            inc_eff=self.multi_sum(inc) + gen_inc
            amp_eff=self.multi_amp_factor(amp) * gen_amp
            const_pair={'Physical':('constPhysInc','constPhysAmp'),'Fire':('constFireInc','constFireAmp'),'Cold':('constColdInc','constColdAmp'),'Lightning':('constLightningInc','constLightningAmp'),'Poison':('constPoisonInc','constPoisonAmp'),'Chaos':(None,None)}[name]
            if const_pair[0]:
                inc_eff += f(self.vars[const_pair[0]].get())
                amp_eff *= (1+f(self.vars[const_pair[1]].get())/100.0)
            mn,mx=self.component(
                name,
                f(self.vars[a].get()),
                f(self.vars[b].get()),
                inc_eff,
                amp_eff,
                s,
                f(self.vars[skillflat].get()),
                f(self.vars[kmn].get()),
                f(self.vars[kmx].get()),
                bmin,
                bmax,
            )
            calc_mn, calc_mx = mn, mx
            if has_entered_tooltip:
                mn, mx = entered_tmin, entered_tmax
                lines.append(f'{name:10} {fmt(mn,mx)} | ВВЕДЁННЫЙ ТУЛТИП (расчёт был {fmt(calc_mn,calc_mx)})')
            else:
                lines.append(f'{name:10} {fmt(mn,mx)} | Increase {inc_eff:.4f}% | Amp ×{amp_eff:.8f}')
            comps[name]=[mn,mx]; direct_min+=mn; direct_max+=mx
        lines.append(f'Direct subtotal (all Increase/Amp applied once): {fmt(direct_min,direct_max)}')

        lines += ['', '2. ТЕГОВЫЕ МОДИФИКАТОРЫ']
        tagdata=[
            ('Area','tagArea','areaInc','areaAmp','areaKMin','areaKMax','constAreaInc','constAreaAmp'),
            ('Projectile','tagProj','projInc','projAmp','projKMin','projKMax','constProjInc','constProjAmp'),
            ('Melee','tagMelee','meleeInc','meleeAmp','meleeKMin','meleeKMax','constMeleeInc','constMeleeAmp'),
            ('Strike','tagStrike','strikeInc','strikeAmp','strikeKMin','strikeKMax','constStrikeInc','constStrikeAmp'),
        ]

        # IMPORTANT:
        # Every tag modifier is calculated from the SAME pre-tag tooltip.
        # Tags are separate modifier pools; they must not compound by using
        # the already-increased result of a previous tag as their base.
        tag_base_min, tag_base_max = direct_min, direct_max
        tag_add_min = tag_add_max = 0.0
        # The Increase side keeps the experimentally established K model.
        # For Amplification, current empirical model: all active tag amps act
        # on one common pre-K pool consisting of the direct tooltip plus the
        # raw tag-Increase portions. This is the best fit to the current Area
        # +5% / Melee +8% paired tests, but remains an experimental model.
        amp_pool_min = tag_base_min
        amp_pool_max = tag_base_max
        tag_amp_factor = 1.0

        for name,ck,ik,ak,kmn,kmx,const_ik,const_ak in tagdata:
            if not self.checks[ck].get():
                lines.append(f'{name}: OFF → Increase/Amplification ignored')
                continue

            # Constellation tag modifiers are additional sources of the SAME
            # tag pools. Increase is additive; Amplification is an independent
            # multiplicative factor. For Area this uses the established Area K
            # coefficient on Increase, while Area Amplification participates in
            # the common tag-amplification pool (not as a standalone K packet).
            inc_sources = self.multi_sum(ik)
            amp_factor = self.multi_amp_factor(ak)
            if const_ik is not None:
                inc_sources += f(self.vars[const_ik].get())
            if const_ak is not None:
                amp_factor *= (1 + f(self.vars[const_ak].get()) / 100.0)

            kmin = f(self.vars[kmn].get()) / 100.0
            kmax = f(self.vars[kmx].get()) / 100.0
            addmin = tag_base_min * kmin * (inc_sources / 100.0)
            addmax = tag_base_max * kmax * (inc_sources / 100.0)
            inc = inc_sources
            amp = amp_factor
            tag_add_min += addmin
            tag_add_max += addmax
            # This raw tag-increase portion belongs to the common amplification
            # pool; the displayed Increase contribution still uses its K.
            amp_pool_min += tag_base_min * (inc / 100.0)
            amp_pool_max += tag_base_max * (inc / 100.0)
            tag_amp_factor *= amp
            lines.append(f'{name}: Inc sum {inc:.4f}% | Amp factor {amp:.8f} → +{fmt(addmin,addmax)}')

        tagged_min = tag_base_min + tag_add_min + amp_pool_min * (tag_amp_factor - 1.0)
        tagged_max = tag_base_max + tag_add_max + amp_pool_max * (tag_amp_factor - 1.0)
        lines.append(f'Tag Amplification common pool: {fmt(amp_pool_min,amp_pool_max)} | factor {tag_amp_factor:.8f} → +{fmt(amp_pool_min*(tag_amp_factor-1.0), amp_pool_max*(tag_amp_factor-1.0))}')
        direct_min, direct_max = tagged_min, tagged_max

        lines += ['', '3. ДОПОЛНИТЕЛЬНЫЙ УРОН']
        totals=dict(comps); separate_min=separate_max=0
        for i in range(1,6):
            if not self.checks[f'sp{i}'].get(): continue
            src=self.vars[f'sp{i}src'].get().strip(); dst=self.vars[f'sp{i}dst'].get().strip(); pct=f(self.vars[f'sp{i}pct'].get())
            if src not in comps or pct==0:
                lines.append(f'Пакет {i}: пропущен — Source не имеет основного tooltip-компонента или % = 0')
                continue
            extra=(comps[src][0]+comps[src][1])/2*pct/100
            if src.lower()==dst.lower():
                old=totals.get(dst,[0,0]); totals[dst]=[old[0]+extra,old[1]+extra]
                lines.append(f'Пакет {i}: {src} → {dst}, {pct:.2f}% среднего → ВХОДИТ: +{extra:.2f}')
            else:
                separate_min+=extra; separate_max+=extra
                lines.append(f'Пакет {i}: {src} → {dst}, {pct:.2f}% среднего → ОТДЕЛЬНО: {extra:.2f}–{extra:.2f}')

        # The tag-adjusted tooltip is authoritative. Same-element packets
        # are then added on top of it.
        main_min, main_max = tagged_min, tagged_max
        for n, v in totals.items():
            original = comps.get(n)
            if original is None:
                continue
            main_min += v[0] - original[0]
            main_max += v[1] - original[1]
        total_min=main_min+separate_min; total_max=main_max+separate_max
        lines += ['', 'Основной tooltip по типам:']
        for n,v in totals.items(): lines.append(f'  {n}: {fmt(v[0],v[1])}')
        lines += [f'MAIN TOOLTIP: {fmt(main_min,main_max)}',f'SEPARATE EXTRA PACKETS: {fmt(separate_min,separate_max)}',f'TOTAL HIT: {fmt(total_min,total_max)}','', '4. ПОСЛЕ ТУЛТИПА']
        d=f(self.vars['doublePct'].get())+f(self.vars['constMaxDmg'].get()); t=f(self.vars['triplePct'].get())+f(self.vars['constTripleDmg'].get()); crit_dmg_pct=f(self.vars['critDmgPct'].get())+f(self.vars['constCritDmg'].get()); cm=1.5 + crit_dmg_pct/100.0; cc=f(self.vars['critChance'].get())
        double_mult = 1 + d/100.0
        triple_mult = 1 + t/100.0
        lines += [
            f'Normal: {fmt(total_min,total_max)}',
            f'Double: {fmt(total_min*double_mult,total_max*double_mult)}',
            f'Triple: {fmt(total_min*triple_mult,total_max*triple_mult)}',
            f'Critical Normal (+{crit_dmg_pct:.2f}% Critical DMG): {fmt(total_min*cm,total_max*cm)}',
            f'Double Critical: {fmt(total_min*double_mult*cm,total_max*double_mult*cm)}',
            f'Triple Critical: {fmt(total_min*triple_mult*cm,total_max*triple_mult*cm)}',
        ]
        ef=1+cc/100*(cm-1)
        lines += ['', 'ПРАВИЛА:','• Для каждого Increase все источники складываются; для каждого Amplification источники перемножаются. Кнопка + добавляет новый независимый источник, − обнуляет его.','• % Урон имеет тот же принцип: дополнительные Increase складываются, дополнительные Amplification перемножаются и затем умножаются на типовой Amp.','• Weapon Range полностью исключён.','• Доп. пакет при Source = Target объединяется с основным tooltip этого типа; при разных стихиях остаётся отдельным.','• 17% packet пока использует проверенную модель: процент от среднего урона источника, без повторного применения target Inc/Amp.']
        self.output.configure(state='normal'); self.output.delete('1.0','end'); self.output.insert('1.0','\n'.join(lines)); self.output.configure(state='disabled')


if __name__ == '__main__':
    App().mainloop()
