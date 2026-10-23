#!/usr/bin/env python3
"""Emotional Atlas — native desktop application. Requires Python 3.10+ with Tk."""
from __future__ import annotations
import csv
import io
import json
import math
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from pca import fit_pca, pca_report
from playback import Timeline, revealed_rows, consecutive_segments
from analysis import (MODEL, AnalysisError, Cancelled, analyze_resilient_batch, batches,
                      export_session, load_session, split_paragraphs, gutenberg_body)

BASE = Path(__file__).resolve().parent
BG = '#1643b8'
PANEL = '#10338c'
TEXT = '#ffffff'
MUTED = '#d7e5ff'
TEAL = '#86f0db'
BLUE = '#9dc8ff'
CORAL = '#ffb3a8'
GOLD = '#ffe59a'
PLOT_BG = '#101b24'
PLOT_TEXT = '#e3ebe8'
PLOT_MUTED = '#97aeb9'


def color(valence):
    a, b = ((243, 155, 148), (153, 176, 188)) if valence < 0 else ((153, 176, 188), (117, 214, 192))
    t = valence + 1 if valence < 0 else valence
    return '#%02x%02x%02x' % tuple(round(x + (y-x)*t) for x, y in zip(a, b))


def number(value, signed=False):
    return 'Unclear' if value is None else (f'{value:+.2f}' if signed else f'{value:.2f}')


def expanded_plot_size(width,height,available_width,available_height):
    factor=min(math.sqrt(2),max(1,available_width)/max(1,width),max(1,available_height)/max(1,height))
    return max(1,round(width*factor)),max(1,round(height*factor)),factor < math.sqrt(2)-1e-9


class EmotionPlot(tk.Canvas):
    """Perspective 3D scatter plot, projected on a Tk canvas with depth sorting."""
    def __init__(self, parent, on_select):
        super().__init__(parent, background=PLOT_BG, highlightthickness=0, height=380, takefocus=True)
        self.on_select = on_select
        self.rows = []
        self.mode = "Emotion axes"
        self.pca = fit_pca([])
        self.cutoff = None
        self.show_trail = False
        self.on_draw = None
        self.selected = None
        self.yaw, self.pitch, self.zoom = -.65, .38, 1.0
        self.points = []
        self.drag = None
        self.moved = False
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<ButtonPress-1>', self.press)
        self.bind('<B1-Motion>', self.motion)
        self.bind('<ButtonRelease-1>', self.release)
        self.bind('<MouseWheel>', self.wheel)
        self.bind('<Button-4>', lambda e: self.set_zoom(1.1))
        self.bind('<Button-5>', lambda e: self.set_zoom(.9))
        self.bind('<Left>', lambda e: self.rotate(-.12, 0))
        self.bind('<Right>', lambda e: self.rotate(.12, 0))
        self.bind('<Up>', lambda e: self.rotate(0, .1))
        self.bind('<Down>', lambda e: self.rotate(0, -.1))
        self.bind('<Key-plus>', lambda e: self.set_zoom(1.1))
        self.bind('<Key-minus>', lambda e: self.set_zoom(.9))

    def rotate(self, yaw, pitch):
        self.yaw += yaw
        self.pitch = min(1.2, max(-1.2, self.pitch + pitch))
        self.draw()

    def reset(self):
        self.yaw, self.pitch, self.zoom = -.65, .38, 1.0
        self.draw()

    def set_zoom(self, factor):
        self.zoom = min(1.8, max(.55, self.zoom * factor))
        self.draw()

    def wheel(self, event):
        self.set_zoom(1.06 if event.delta > 0 else 1/1.06)

    def press(self, event):
        self.focus_set()
        self.drag = (event.x, event.y)
        self.moved = False

    def motion(self, event):
        if self.drag:
            dx, dy = event.x-self.drag[0], event.y-self.drag[1]
            if abs(dx)+abs(dy) > 2:
                self.moved = True
            self.rotate(dx*.008, dy*.008)
            self.drag = (event.x, event.y)

    def release(self, event):
        if not self.moved:
            near = [(math.hypot(x-event.x, y-event.y), -depth, row) for x,y,depth,row in self.points]
            if near:
                distance, _, row = min(near, key=lambda item: (item[0], item[1]))
                if distance < 17:
                    self.on_select(row['id'])
        self.drag = None

    def project(self, point):
        x, y, z = point
        if self.mode == 'PCA 2D':
            scale=min(self.winfo_width()*.32,self.winfo_height()*.33)*self.zoom
            return self.winfo_width()/2+x*scale,self.winfo_height()/2-y*scale,0
        x1 = x*math.cos(self.yaw) - y*math.sin(self.yaw)
        y1 = x*math.sin(self.yaw) + y*math.cos(self.yaw)
        up = z*math.cos(self.pitch) - y1*math.sin(self.pitch)
        depth = y1*math.cos(self.pitch) + z*math.sin(self.pitch)
        scale = min(self.winfo_width()*.23, self.winfo_height()*.29)*self.zoom * 5/(5+depth)
        return self.winfo_width()/2 + x1*scale, self.winfo_height()/2-up*scale+8, depth

    def line3(self, a, b, fill, width=1, dash=None):
        x,y,_ = self.project(a)
        u,v,_ = self.project(b)
        self.create_line(x,y,u,v,fill=fill,width=width,dash=dash)

    def label3(self, p, text, fill=PLOT_MUTED):
        x,y,_=self.project(p)
        self.create_text(x,y,text=text,fill=fill,font=('Menlo',10),justify='center')

    def coordinate(self,row):
        if self.mode == 'Emotion axes':
            return (row['valence'],row['direction'],row['intensity']*2-1) if row['direction'] is not None else None
        score=self.pca['scores'].get(row['id'])
        return tuple(x/self.pca['scale'] for x in score) if score is not None else None

    def draw(self):
        self.delete('all')
        if self.mode == 'PCA 2D':
            for tick in (-1,-.5,0,.5,1):
                self.line3((tick,-1,0),(tick,1,0),'#2a3c48')
                self.line3((-1,tick,0),(1,tick,0),'#2a3c48')
            self.line3((-1,0,0),(1,0,0),PLOT_MUTED)
            self.line3((0,-1,0),(0,1,0),PLOT_MUTED)
        else:
            for tick in (-1,-.5,0,.5,1):
                self.line3((tick,-1,-1),(tick,1,-1),'#2a3c48')
                self.line3((-1,tick,-1),(1,tick,-1),'#2a3c48')
            for x in (-1,1):
                for y in (-1,1):
                    self.line3((x,y,-1),(x,y,1),'#283a46',dash=(3,5))
            self.line3((-1,-1,-1),(1,-1,-1),'#9cb9b4',2)
            self.line3((-1,-1,-1),(-1,1,-1),'#9cb9b4',2)
            self.line3((-1,-1,-1),(-1,-1,1),'#9cb9b4',2)
        if self.mode == 'Emotion axes':
            self.label3((0,-1.45,-1),'VALENCE  −1 → +1')
            self.label3((-1.45,0,-1),'DIRECTION\ninward −1 / outward +1')
            self.label3((-1.1,-1.1,1.28),'INTENSITY  1')
            self.label3((-1,-1,-1.25),'0')
        elif not self.pca['error']:
            labels=[f'PC{i+1} ({ratio:.1%})' for i,ratio in enumerate(self.pca['ratios'])]
            if self.mode == 'PCA 2D':
                self.label3((0,-1.22,0),labels[0]);self.label3((-1.24,.85,0),labels[1])
            else:
                self.label3((0,-1.35,-1),labels[0]);self.label3((-1.35,0,-1),labels[1]);self.label3((-1,-1,1.25),labels[2])
            self.create_text(self.winfo_width()-16,18,anchor='ne',fill=PLOT_MUTED,font=('Menlo',10),text=f"Axis bounds ±{self.pca['scale']:.2f} PC units")
        revealed = revealed_rows(self.rows, self.cutoff)
        known = [r for r in revealed if self.coordinate(r) is not None]
        if self.show_trail:
            for a,b in consecutive_segments(known):
                self.line3(self.coordinate(a),self.coordinate(b), '#526e79', 1)
        self.points = []
        projected = [(self.project(self.coordinate(r)),r) for r in known]
        for (x,y,depth),row in sorted(projected,key=lambda item: -item[0][2]):
            size=5 if row['id'] != self.selected else 8
            self.create_oval(x-size,y-size,x+size,y+size,fill=color(row['valence']),
                             outline=PLOT_TEXT if row['id']==self.selected else PLOT_BG,width=2)
            self.points.append((x,y,depth,row))
            if row['id']==self.selected:
                self.create_text(x+12,y-12,text=f"¶ {row['id']}",fill=PLOT_TEXT,anchor='w',font=('Menlo',11,'bold'))
        unknown=len(revealed)-len(known)
        self.create_text(18,18,anchor='nw',fill=PLOT_MUTED,font=('Menlo',10),
                         text=f'{len(known)} plotted · {unknown} without plot coordinates' + (f' · through ¶ {self.cutoff}' if self.cutoff is not None else ''))
        if self.mode != 'Emotion axes' and self.pca['error']:
            self.create_text(self.winfo_width()/2,self.winfo_height()/2,text=self.pca['error'],
                             fill=PLOT_TEXT,font=('Menlo',12),width=max(200,self.winfo_width()-80))
        elif not self.rows:
            self.create_text(self.winfo_width()/2,self.winfo_height()/2-24,
                text='Your emotional landscape starts here', fill=PLOT_TEXT,font=('Menlo',17,'bold'))
            self.create_text(self.winfo_width()/2,self.winfo_height()/2+6,
                text='Analyze text to map each paragraph in three dimensions.',fill=PLOT_MUTED,font=('Menlo',11))
        self.create_text(18,self.winfo_height()-18,anchor='sw',fill=PLOT_MUTED,
            text=('Scroll to zoom · Click a point to inspect' if self.mode == 'PCA 2D' else 'Drag to rotate · Scroll to zoom · Click a point to inspect'),font=('Menlo',10))
        if self.on_draw is not None:self.on_draw()


class Atlas(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Emotional Atlas v0.1 · GPT-6 Luna')
        self.geometry('1390x920')
        self.minsize(1030,720)
        self.configure(background=BG)
        icon_path=BASE/'assets'/'emotion-atlas-icon-small.png'
        if icon_path.exists():
            self.app_icon=tk.PhotoImage(file=str(icon_path))
            self.iconphoto(True,self.app_icon)
        self.expanded_window=None
        self.expanded_plot=None
        self.paragraphs=[]
        self.results={};self.reviews={}
        self.title_text='Untitled text'
        self.usage={'input_tokens':0,'output_tokens':0}
        self.events=queue.Queue()
        self.cancel=threading.Event()
        self.running=False
        self.dirty=False
        self.mode_used='blank'
        self.session_text=''
        self.current_id=None
        self.timeline=Timeline()
        self.playback_timer=None
        self.playback_speed=tk.StringVar(value='2')
        self.playback_position=tk.DoubleVar(value=0)
        self.playback_label=tk.StringVar(value='All paragraphs visible')
        self.trail=tk.BooleanVar(value=False)
        self.plot_mode=tk.StringVar(value='Emotion axes')
        self.pca_signature=None
        self.key=tk.StringVar()
        self.status=tk.StringVar(value='Ready. Add text and your API key to begin.')
        self.stats=tk.StringVar(value='0 paragraphs  /  0 analyzed')
        self.filter=tk.StringVar(value='All paragraphs')
        self.mode=tk.StringVar(value='Blank lines')
        self.range_count=tk.StringVar(value='All remaining')
        self.configure_styles()
        self.build()
        self.after(100,self.poll)
        self.protocol('WM_DELETE_WINDOW',self.close)

    def configure_styles(self):
        style=ttk.Style(self);style.theme_use('clam')
        style.configure('.',background=BG,foreground=TEXT,font=('Menlo',10),borderwidth=1)
        style.configure('TFrame',background=BG)
        style.configure('Panel.TFrame',background=PANEL)
        style.configure('Card.TFrame',background=PANEL,padding=10,relief='solid',borderwidth=1,bordercolor='#83afff')
        style.configure('TLabel',background=BG,foreground=TEXT)
        style.configure('Muted.TLabel',foreground=MUTED,font=('Menlo',10))
        style.configure('Title.TLabel',font=('Menlo',23,'bold'),foreground=TEXT)
        style.configure('Heading.TLabel',font=('Menlo',12,'bold'),foreground='#ffffff')
        style.configure('TButton',background='#245bd1',foreground=TEXT,padding=(10,7),borderwidth=2,relief='raised',bordercolor='#95bbff',lightcolor='#95bbff',darkcolor='#08236b')
        style.map('TButton',background=[('disabled','#294993'),('pressed','#0d2d80'),('active','#3275ed')],foreground=[('disabled','#a6b8e1'),('active',TEXT)],relief=[('pressed','sunken')])
        style.configure('Accent.TButton',background='#a9d3ff',foreground='#072465')
        style.map('Accent.TButton',background=[('disabled','#294993'),('pressed','#78b6ff'),('active','#c4e5ff')],foreground=[('disabled','#a6b8e1')])
        style.configure('TEntry',fieldbackground=PANEL,foreground=TEXT,insertcolor=TEXT,padding=8,borderwidth=2,bordercolor='#95bbff',lightcolor='#95bbff',darkcolor='#08236b')
        style.configure('TCombobox',fieldbackground=PANEL,background='#245bd1',foreground=TEXT,arrowcolor=TEXT,padding=6,borderwidth=2,bordercolor='#95bbff',lightcolor='#95bbff',darkcolor='#08236b')
        style.map('TCombobox',fieldbackground=[('readonly',PANEL)],foreground=[('readonly',TEXT)])
        self.option_add('*TCombobox*Listbox.background',PANEL)
        self.option_add('*TCombobox*Listbox.foreground',TEXT)
        self.option_add('*TCombobox*Listbox.selectBackground','#a9d3ff')
        self.option_add('*TCombobox*Listbox.selectForeground','#072465')
        style.configure('Treeview',fieldbackground=PANEL,background=PANEL,foreground=TEXT,rowheight=29)
        style.configure('Treeview.Heading',background='#245bd1',foreground=TEXT,padding=7,relief='raised')
        style.map('Treeview',background=[('selected','#a9d3ff')],foreground=[('selected','#072465')])
        style.configure('TNotebook',background=BG,borderwidth=1)
        style.configure('TNotebook.Tab',background='#10338c',foreground=MUTED,padding=(14,8))
        style.map('TNotebook.Tab',background=[('selected','#245bd1')],foreground=[('selected',TEXT)])
        style.configure('TCheckbutton',background=BG,foreground=TEXT)
        style.map('TCheckbutton',background=[('active',BG)])
        style.configure('TSeparator',background='#83afff')
        style.configure('Horizontal.TProgressbar',background='#a9d3ff',troughcolor=PANEL)
        style.configure('Horizontal.TScale',background='#a9d3ff',troughcolor=PANEL)
        style.layout('Modern.Vertical.TScrollbar',[
            ('Vertical.Scrollbar.trough',{'sticky':'ns','children':[
                ('Vertical.Scrollbar.thumb',{'sticky':'nswe','expand':True})]})])
        style.configure('Modern.Vertical.TScrollbar',width=12,troughcolor=PANEL,
                        background='#7caeff',borderwidth=1,arrowsize=0,relief='flat',
                        bordercolor='#c1dcff',lightcolor='#c1dcff',darkcolor='#17428e')
        style.map('Modern.Vertical.TScrollbar',background=[('pressed','#d5eaff'),('active','#a9d3ff')])

    def build(self):
        top=ttk.Frame(self,padding=(22,18,22,12)); top.pack(fill='x')
        ttk.Label(top,text='◈  Emotional Atlas',style='Title.TLabel').pack(side='left')
        ttk.Label(top,text='DREAMS  /  LITERATURE  /  SEMANTIC INFERENCE',style='Muted.TLabel').pack(side='left',padx=22)
        ttk.Button(top,text='Method',command=self.method).pack(side='right')
        outer=ttk.Panedwindow(self,orient='horizontal'); outer.pack(fill='both',expand=True,padx=18)
        left=ttk.Frame(outer,width=360,padding=(0,0,16,0)); outer.add(left,weight=0)
        right=ttk.Frame(outer); outer.add(right,weight=1)
        ttk.Label(left,text='01  Source text',style='Heading.TLabel').pack(anchor='w',pady=(4,12))
        row=ttk.Frame(left); row.pack(fill='x')
        self.open_btn=ttk.Button(row,text='Open .txt',command=self.open_text);self.open_btn.pack(side='left')
        ttk.Label(left,text='Or paste a dream or passage below.',style='Muted.TLabel').pack(anchor='w',pady=(12,6))
        source_card=ttk.Frame(left,style='Card.TFrame');source_card.pack(fill='both',expand=True)
        self.source=tk.Text(source_card,wrap='word',width=38,height=17,background=PANEL,foreground=TEXT,
            insertbackground=TEXT,selectbackground='#a9d3ff',selectforeground='#072465',highlightthickness=0,relief='flat',padx=12,pady=12,font=('Menlo',12),undo=True)
        source_scroll=ttk.Scrollbar(source_card,orient='vertical',style='Modern.Vertical.TScrollbar',command=self.source.yview)
        source_scroll.pack(side='right',fill='y',padx=(5,0))
        self.source.configure(yscrollcommand=source_scroll.set)
        self.source.pack(fill='both',expand=True)
        self.source.bind('<<Modified>>',self.text_modified)
        opts=ttk.Frame(left);opts.pack(fill='x',pady=10)
        ttk.Label(opts,text='Paragraph breaks',style='Muted.TLabel').pack(side='left')
        self.mode_box=ttk.Combobox(opts,textvariable=self.mode,values=['Blank lines','Every line'],state='readonly',width=12)
        self.mode_box.pack(side='right');self.mode_box.bind('<<ComboboxSelected>>',lambda e:self.update_count())
        ttk.Label(left,textvariable=self.stats,style='Muted.TLabel').pack(anchor='w')
        ttk.Separator(left).pack(fill='x',pady=15)
        ttk.Label(left,text='02  Inference',style='Heading.TLabel').pack(anchor='w',pady=(0,10))
        ttk.Label(left,text='OpenAI API key · held in memory only',style='Muted.TLabel').pack(anchor='w')
        self.key_entry=ttk.Entry(left,textvariable=self.key,show='•');self.key_entry.pack(fill='x',pady=(6,8))
        ttk.Label(left,text='Model: gpt-6-luna  ·  API usage is billed to your key.',style='Muted.TLabel').pack(anchor='w')
        ttk.Label(left,text='Analyze sends text + nearby context to OpenAI.\nNothing is saved locally until you export a session.',style='Muted.TLabel',wraplength=330).pack(anchor='w',pady=8)
        self.range_box=ttk.Combobox(left,textvariable=self.range_count,values=['First 12 remaining','First 60 remaining','All remaining'],state='readonly')
        self.range_box.pack(fill='x',pady=(0,8))
        run=ttk.Frame(left);run.pack(fill='x')
        self.run_btn=ttk.Button(run,text='Analyze / Resume',style='Accent.TButton',command=self.start);self.run_btn.pack(side='left',fill='x',expand=True)
        self.stop_btn=ttk.Button(run,text='Stop',command=self.stop,state='disabled');self.stop_btn.pack(side='left',padx=(8,0))
        ttk.Separator(left).pack(fill='x',pady=14)
        exports=ttk.Frame(left);exports.pack(fill='x')
        ttk.Button(exports,text='Save session',command=self.save_session).pack(side='left')
        self.load_btn=ttk.Button(exports,text='Open session',command=self.open_session);self.load_btn.pack(side='left',padx=6)
        ttk.Button(left,text='Export scores to CSV',command=self.save_csv).pack(fill='x',pady=(8,0))
        header=ttk.Frame(right);header.pack(fill='x',pady=(4,8))
        ttk.Label(header,text='03  Emotional landscape',style='Heading.TLabel').pack(side='left')
        ttk.Button(header,text='Reset view',command=lambda:self.plot.reset()).pack(side='right')
        self.expand_btn=ttk.Button(header,text='Expand plot 2×',command=self.toggle_expanded_plot)
        self.expand_btn.pack(side='right',padx=6)
        view_controls=ttk.Frame(right);view_controls.pack(fill='x',pady=(0,5))
        ttk.Label(view_controls,text='View',style='Muted.TLabel').pack(side='left',padx=(0,6))
        view=ttk.Combobox(view_controls,textvariable=self.plot_mode,values=['Emotion axes','PCA 2D','PCA 3D'],state='readonly',width=16)
        view.pack(side='left');view.bind('<<ComboboxSelected>>',lambda e:self.change_plot_mode())
        ttk.Button(view_controls,text='PCA details',command=self.show_pca_details).pack(side='left',padx=6)
        ttk.Button(view_controls,text='Export PCA',command=self.export_pca).pack(side='left')
        self.plot=EmotionPlot(right,self.select);self.plot.pack(fill='both',expand=True)
        self.plot.on_draw=self.sync_expanded_plot

        legend=ttk.Frame(right);legend.pack(fill='x',pady=6)
        ttk.Label(legend,text='● Negative',foreground=CORAL).pack(side='left',padx=8)
        ttk.Label(legend,text='● Neutral',foreground=MUTED).pack(side='left',padx=8)
        ttk.Label(legend,text='● Positive',foreground=TEAL).pack(side='left',padx=8)
        ttk.Label(legend,text='One point = one paragraph',style='Muted.TLabel').pack(side='right',padx=10)
        playback=ttk.Frame(right);playback.pack(fill='x',pady=(4,4))
        self.play_btn=ttk.Button(playback,text='▶ Play',command=self.toggle_playback)
        self.play_btn.pack(side='left')
        ttk.Button(playback,text='↺ Restart',command=self.restart_playback).pack(side='left',padx=5)
        ttk.Button(playback,text='Show all',command=self.show_all_points).pack(side='left')
        ttk.Label(playback,text='Paragraphs / sec',style='Muted.TLabel').pack(side='left',padx=(14,5))
        speed=ttk.Combobox(playback,textvariable=self.playback_speed,values=['0.25','0.5','1','2','5','10'],state='readonly',width=5)
        speed.pack(side='left');speed.bind('<<ComboboxSelected>>',lambda e:self.reschedule_playback())
        ttk.Checkbutton(playback,text='Connect neighbors',variable=self.trail,command=self.update_trail).pack(side='right')
        position=ttk.Frame(right);position.pack(fill='x',pady=(0,5))
        self.position_scale=ttk.Scale(position,from_=0,to=1,variable=self.playback_position,command=self.scrub_playback)
        self.position_scale.pack(side='left',fill='x',expand=True,padx=(0,10))
        ttk.Label(position,textvariable=self.playback_label,style='Muted.TLabel',width=43).pack(side='right')
        notebook=ttk.Notebook(right);notebook.pack(fill='both',expand=True,pady=(4,0))
        table_frame=ttk.Frame(notebook);notebook.add(table_frame,text='Paragraphs')
        detail_frame=ttk.Frame(notebook);notebook.add(detail_frame,text='Evidence & decomposition')
        self.notebook=notebook
        controls=ttk.Frame(table_frame);controls.pack(fill='x',pady=7)
        ttk.Label(controls,text='Show',style='Muted.TLabel').pack(side='left',padx=6)
        filters=ttk.Combobox(controls,textvariable=self.filter,values=['All paragraphs','Positive','Negative','Mixed','Uncertain direction','Needs review','Not analyzed'],state='readonly',width=21)
        filters.pack(side='left');filters.bind('<<ComboboxSelected>>',lambda e:self.refresh())
        ttk.Button(controls,text='Inspect selected →',command=self.inspect).pack(side='right')
        columns=('id','emotion','intensity','valence','direction','uncertainty')
        table_card=ttk.Frame(table_frame,style='Card.TFrame');table_card.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(table_card,columns=columns,show='headings',height=7,selectmode='browse')
        for col,name,width in zip(columns,['¶','Emotions','Intensity','Valence','Direction','Uncertainty'],[45,190,75,75,95,85]):
            self.tree.heading(col,text=name);self.tree.column(col,width=width,minwidth=40,stretch=col=='emotion')
        scroll=ttk.Scrollbar(table_card,orient='vertical',style='Modern.Vertical.TScrollbar',command=self.tree.yview);scroll.pack(side='right',fill='y')
        self.tree.configure(yscrollcommand=scroll.set);self.tree.pack(fill='both',expand=True)
        self.tree.bind('<<TreeviewSelect>>',self.tree_select);self.tree.bind('<Double-1>',lambda e:self.inspect())
        detail_card=ttk.Frame(detail_frame,style='Card.TFrame');detail_card.pack(fill='both',expand=True,pady=6)
        self.detail=tk.Text(detail_card,wrap='word',height=12,background=PANEL,foreground=TEXT,
            relief='flat',highlightthickness=0,selectbackground='#a9d3ff',selectforeground='#072465',padx=8,pady=6,font=('Menlo',12),state='disabled')
        detail_scroll=ttk.Scrollbar(detail_card,orient='vertical',style='Modern.Vertical.TScrollbar',command=self.detail.yview);detail_scroll.pack(side='right',fill='y')
        self.detail.configure(yscrollcommand=detail_scroll.set);self.detail.pack(fill='both',expand=True)
        self.detail.tag_configure('heading',font=('Menlo',13,'bold'),foreground=BLUE,spacing1=12,spacing3=8)
        self.detail.tag_configure('muted',foreground=MUTED,spacing3=8)
        self.detail.tag_configure('signal',background='#fff0bc',foreground='#483b12')
        self.detail.tag_configure('quote',foreground=GOLD,spacing1=4,spacing3=6)
        foot=ttk.Frame(self,padding=(20,9));foot.pack(fill='x')
        self.progress=ttk.Progressbar(foot,mode='determinate',length=170);self.progress.pack(side='right')
        ttk.Label(foot,textvariable=self.status,style='Muted.TLabel',wraplength=1040).pack(side='left')

    def text_modified(self,event=None):
        if self.source.edit_modified():
            self.source.edit_modified(False)
            self.update_count()

    def update_count(self):
        raw=self.source.get('1.0','end-1c')
        parts=split_paragraphs(raw,self.mode_code())
        n=len(self.results) if parts==self.paragraphs else 0
        self.stats.set(f'{len(parts):,} paragraphs  /  {n:,} analyzed')
        if self.results and parts!=self.paragraphs and not self.running:
            self.status.set('Source changed. Displayed results belong to the previous text; Analyze will start a new session.')

    def mode_code(self):
        return 'blank' if self.mode.get()=='Blank lines' else 'line'

    def confirm_replace(self):
        if self.dirty:
            return messagebox.askyesno('Unsaved analysis','Replace the current analysis? Save a session first if you want to keep it.',parent=self)
        return True

    def set_source(self,text,title):
        self.pause_playback()
        self.timeline.reset()
        self.source.configure(state='normal');self.source.delete('1.0','end');self.source.insert('1.0',text)
        self.paragraphs=split_paragraphs(text,self.mode_code());self.results={};self.reviews={};self.current_id=None
        self.session_text=text;self.title_text=title;self.usage={'input_tokens':0,'output_tokens':0};self.dirty=False
        self.refresh();self.status.set(f'Loaded {title}. Ready for GPT-6 Luna analysis.')

    def open_text(self):
        if not self.confirm_replace():return
        path=filedialog.askopenfilename(filetypes=[('Text files','*.txt'),('All files','*')])
        if path:
            try:self.set_source(Path(path).read_text(encoding='utf-8-sig'),Path(path).name)
            except (OSError,UnicodeError) as e:messagebox.showerror('Cannot open text',f'Use a UTF-8 plain text file.\n{e}')

    def start(self):
        if self.running:return
        key=self.key.get().strip()
        if not key:messagebox.showinfo('API key needed','Enter your OpenAI API key. It stays in memory and is never included in exports.');return
        paragraphs=split_paragraphs(self.source.get('1.0','end-1c'),self.mode_code())
        if not paragraphs:messagebox.showinfo('Add text','Paste text or open a UTF-8 .txt file first.');return
        if paragraphs!=self.paragraphs:
            if not self.confirm_replace():return
            self.pause_playback();self.timeline.reset()
            self.results={};self.reviews={};self.usage={'input_tokens':0,'output_tokens':0};self.dirty=False;self.current_id=None
            self.paragraphs=paragraphs
            self.title_text='Custom text'
        try:groups=list(batches(self.paragraphs,self.results))
        except AnalysisError as e:messagebox.showerror('Text needs paragraph breaks',str(e));return
        maximum={'First 12 remaining':12,'First 60 remaining':60}.get(self.range_count.get())
        if maximum:
            limited=[];count=0
            for group in groups:
                if count>=maximum:break
                group=group[:maximum-count];limited.append(group);count+=len(group)
            groups=limited
        if not groups:self.status.set('All paragraphs have already been analyzed.');return
        self.cancel.clear();self.running=True;self.set_running(True);self.refresh()
        self.status.set(f'Analyzing {sum(len(g) for g in groups)} paragraphs using GPT-6 Luna…')
        def worker():
            review_count=0
            try:
                for group in groups:
                    if self.cancel.is_set():break
                    self.events.put(('status',f"Inferring paragraphs {group[0]['id']}–{group[-1]['id']} with GPT-6 Luna…"))
                    for event in analyze_resilient_batch(group,key,self.cancel,lambda s:self.events.put(('status',s))):
                        if event[0]=='review':review_count+=1
                        self.events.put(event)
                self.events.put(('done','Stopped. Completed results retained; Analyze / Resume continues.' if self.cancel.is_set() else f'Run finished. {review_count} paragraph(s) need review; verified results retained. Save a session to keep the results.'))
            except Cancelled:self.events.put(('done','Stopped. Completed results retained.'))
            except Exception as e:
                message=str(e) if isinstance(e,AnalysisError) else 'Analysis stopped due to an unexpected response. Completed results are retained.'
                self.events.put(('error',message))
        threading.Thread(target=worker,daemon=True).start()

    def stop(self):
        self.cancel.set();self.stop_btn.configure(state='disabled')
        self.status.set('Stopping after the current API request completes (up to 150 seconds)…')

    def set_running(self,running):
        state='disabled' if running else 'normal'
        for btn in (self.open_btn,self.run_btn,self.load_btn):btn.configure(state=state)
        self.source.configure(state=state);self.key_entry.configure(state=state)
        self.mode_box.configure(state='disabled' if running else 'readonly')
        self.range_box.configure(state='disabled' if running else 'readonly')
        self.stop_btn.configure(state='normal' if running else 'disabled')

    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='status':
                    if not self.cancel.is_set():self.status.set(value)
                elif kind=='result':
                    rows,usage=value
                    self.results.update({r['id']:r for r in rows});self.dirty=True
                    for r in rows:self.reviews.pop(r['id'],None)
                    for k in ('input_tokens','output_tokens'):
                        self.usage[k]+=usage.get(k,0)
                    if self.current_id is None and rows:self.current_id=rows[0]['id']
                    self.refresh()
                elif kind=='review':
                    index,reason=value;self.reviews[index]=reason;self.dirty=True
                    self.refresh()
                elif kind in ('done','error'):
                    self.running=False;self.set_running(False);self.status.set(value)
                    if kind=='error':messagebox.showerror('Analysis paused',value,parent=self)
        except queue.Empty:pass
        self.after(100,self.poll)

    def visible(self,index,result):
        selected=self.filter.get()
        if selected=='All paragraphs':return True
        if selected=='Needs review':return index in self.reviews
        if selected=='Not analyzed':return result is None
        if not result:return False
        if selected=='Uncertain direction':return result['direction'] is None
        return result['tone']==selected.lower()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        rows=[]
        for i in range(1,len(self.paragraphs)+1):
            r=self.results.get(i)
            if not self.visible(i,r):continue
            if r:
                rows.append(r)
                labels=', '.join(e['label'] for e in r['emotions']) or 'No emotion conveyed'
                values=(i,labels,number(r['intensity']),number(r['valence'],True),r['direction_status'],r['uncertainty'])
            else:values=(i,'Needs review' if i in self.reviews else 'Not analyzed','—','—','—','—')
            self.tree.insert('', 'end',iid=str(i),values=values)
        self.timeline.total=len(self.paragraphs)
        self.position_scale.configure(to=max(1,len(self.paragraphs)))
        signature=tuple((i,r['valence'],r['direction'],r['intensity']) for i,r in sorted(self.results.items()))
        if signature != self.pca_signature:
            if self.timeline.playing and self.plot.mode != 'Emotion axes':self.pause_playback()
            self.plot.pca=fit_pca(list(self.results.values()));self.pca_signature=signature
        self.plot.rows=rows;self.plot.selected=self.current_id
        self.plot.cutoff=self.timeline.position;self.plot.draw()
        self.update_playback_label()
        self.stats.set(f'{len(self.paragraphs):,} paragraphs  /  {len(self.results):,} analyzed  /  {len(self.reviews)} need review')
        self.progress.configure(maximum=max(1,len(self.paragraphs)),value=len(self.results))
        if self.current_id:
            if self.tree.exists(str(self.current_id)):self.tree.selection_set(str(self.current_id))
            self.show_detail(self.current_id)
        else:
            self.detail.configure(state='normal');self.detail.delete('1.0','end')
            self.detail.insert('end','Select a paragraph to inspect its source text and model evidence.','muted');self.detail.configure(state='disabled')

    def tree_select(self,event=None):
        selected=self.tree.selection()
        if selected:
            index=int(selected[0])
            if self.timeline.position is not None and index != self.current_id:
                self.pause_playback();self.timeline.seek(index);self.plot.cutoff=index
                self.update_playback_label()
            self.current_id=index;self.plot.selected=index;self.plot.draw();self.show_detail(index)

    def select(self,index):
        self.pause_playback()
        self.current_id=index
        if self.tree.exists(str(index)):
            self.tree.selection_set(str(index));self.tree.see(str(index))
        self.plot.selected=index;self.plot.draw();self.show_detail(index);self.notebook.select(1)

    def toggle_expanded_plot(self):
        if self.expanded_window is not None:
            self.close_expanded_plot();return
        self.update_idletasks()
        # Double canvas area while retaining aspect ratio; fit smaller screens honestly.
        width,height,fitted=expanded_plot_size(self.plot.winfo_width(),self.plot.winfo_height(),
                                              self.winfo_screenwidth()-80,self.winfo_screenheight()-240)
        win=tk.Toplevel(self);self.expanded_window=win
        win.title('Emotional Atlas · Expanded plot');win.configure(background=BG)
        win.geometry(f'{width}x{height+132}')
        win.protocol('WM_DELETE_WINDOW',self.close_expanded_plot)
        win.bind('<Escape>',lambda event:self.close_expanded_plot())
        toolbar=ttk.Frame(win,padding=(10,8));toolbar.pack(fill='x')
        ttk.Label(toolbar,text='Expanded plot · '+('fit to screen' if fitted else '2× display area'),style='Heading.TLabel').pack(side='left')
        ttk.Button(toolbar,text='Restore plot',command=self.close_expanded_plot).pack(side='right')
        ttk.Button(toolbar,text='Play / Pause',command=self.toggle_playback).pack(side='right',padx=5)
        ttk.Button(toolbar,text='Reset view',command=lambda:self.expanded_plot.reset()).pack(side='right')
        self.expanded_plot=EmotionPlot(win,self.select)
        self.expanded_plot.configure(width=width,height=height)
        self.expanded_plot.pack(fill='both',expand=True)
        self.expanded_plot.yaw,self.expanded_plot.pitch,self.expanded_plot.zoom=self.plot.yaw,self.plot.pitch,self.plot.zoom
        footer=ttk.Frame(win,padding=(12,8));footer.pack(fill='x')
        self.expanded_caption=tk.StringVar(value='')
        ttk.Label(footer,textvariable=self.expanded_caption,wraplength=max(200,width-30),style='Muted.TLabel').pack(anchor='w')
        self.expand_btn.configure(text='Restore plot')
        self.sync_expanded_plot()

    def sync_expanded_plot(self):
        if self.expanded_plot is None:return
        target=self.expanded_plot
        if target.mode != self.plot.mode:
            target.yaw,target.pitch,target.zoom=self.plot.yaw,self.plot.pitch,self.plot.zoom
        for attr in ('rows','cutoff','show_trail','selected','mode','pca'):
            setattr(target,attr,getattr(self.plot,attr))
        target.draw()
        index=self.plot.selected
        if index and 1<=index<=len(self.paragraphs):
            excerpt=self.paragraphs[index-1]
            self.expanded_caption.set(f'¶ {index}: '+excerpt[:240]+('…' if len(excerpt)>240 else ''))
        else:self.expanded_caption.set('Drag to rotate · Scroll to zoom · Click a point for its paragraph. Full evidence appears in the main window.')

    def close_expanded_plot(self):
        win=self.expanded_window
        self.expanded_plot=None;self.expanded_window=None
        if win is not None:win.destroy()
        self.expand_btn.configure(text='Expand plot 2×')

    def change_plot_mode(self):
        self.pause_playback();self.plot.mode=self.plot_mode.get();self.plot.reset()
        self.refresh()

    def show_pca_details(self):
        messagebox.showinfo('PCA components and interpretation',pca_report(self.plot.pca),parent=self)

    def export_pca(self):
        model=self.plot.pca
        if model['error']:
            messagebox.showinfo('PCA unavailable',model['error'],parent=self);return
        path=filedialog.asksaveasfilename(defaultextension='.json',initialfile='emotion-atlas-pca.json',filetypes=[('PCA data and component weights','*.json')])
        if path:
            try:
                Path(path).write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8')
                self.status.set('PCA exported: paragraph IDs, coordinates, component weights, means, scales, and explained variance.')
            except OSError as e:messagebox.showerror('Export failed',str(e))

    def update_trail(self):
        self.plot.show_trail=self.trail.get();self.plot.draw()

    def pause_playback(self):
        self.timeline.pause()
        if self.playback_timer is not None:
            self.after_cancel(self.playback_timer);self.playback_timer=None
        self.play_btn.configure(text='▶ Play')

    def toggle_playback(self):
        if self.timeline.playing:
            self.pause_playback();return
        self.timeline.total=len(self.paragraphs)
        if not self.results:
            self.status.set('Analyze text or open a saved session before starting playback.');return
        if self.timeline.play():
            self.play_btn.configure(text='❚❚ Pause')
            self.playback_frame()
            self.reschedule_playback()

    def restart_playback(self):
        self.pause_playback();self.timeline.seek(0)
        self.playback_frame()
        self.toggle_playback()

    def show_all_points(self):
        self.pause_playback();self.timeline.reset(len(self.paragraphs))
        self.plot.cutoff=None;self.plot.draw();self.update_playback_label()

    def scrub_playback(self,value):
        self.pause_playback();self.timeline.seek(round(float(value)))
        self.playback_frame()

    def reschedule_playback(self):
        if self.playback_timer is not None:
            self.after_cancel(self.playback_timer);self.playback_timer=None
        if self.timeline.playing:
            self.playback_timer=self.after(round(1000/float(self.playback_speed.get())),self.playback_tick)

    def playback_tick(self):
        self.playback_timer=None
        if self.timeline.advance():self.playback_frame()
        if self.timeline.playing:self.reschedule_playback()
        else:self.play_btn.configure(text='▶ Play')

    def update_playback_label(self):
        position=self.timeline.position
        self.playback_position.set(self.timeline.total if position is None else position)
        if position is None:
            self.playback_label.set('All paragraphs visible');return
        label=f'¶ {position} / {self.timeline.total}'
        if position:
            r=self.results.get(position)
            if r is None:label+=' · needs review' if position in self.reviews else ' · not analyzed'
            elif not self.visible(position,r):label+=' · hidden by filter'
            elif self.plot.coordinate(r) is None:label+=' · no coordinates; not plotted'
            else:label+=f" · {r['tone']} · valence {r['valence']:+.2f}"
        else:label+=' · beginning'
        self.playback_label.set(label)

    def playback_frame(self):
        position=self.timeline.position
        self.plot.cutoff=position
        self.current_id=position if position else None
        self.plot.selected=self.current_id;self.plot.draw();self.update_playback_label()
        if position:
            if self.tree.exists(str(position)):
                self.tree.selection_set(str(position));self.tree.see(str(position))
            else:self.tree.selection_remove(*self.tree.selection())
            self.show_detail(position)
        else:
            self.tree.selection_remove(*self.tree.selection())
            self.detail.configure(state='normal');self.detail.delete('1.0','end')
            self.detail.insert('end','Playback begins before paragraph 1.','muted')
            self.detail.configure(state='disabled')

    def inspect(self):
        if self.current_id:self.notebook.select(1)

    def show_detail(self,index):
        self.detail.configure(state='normal');self.detail.delete('1.0','end')
        self.detail.insert('end',f'Paragraph {index}\n','heading')
        r=self.results.get(index)
        if r:
            self.detail.insert('end',f"Intensity {number(r['intensity'])}  ·  Valence {number(r['valence'],True)}  ·  Direction {number(r['direction'],True)} ({r['direction_status']})\n",'muted')
            if self.plot.mode != 'Emotion axes':
                score=self.plot.pca['scores'].get(index)
                if score is not None:
                    self.detail.insert('end', 'PCA coordinates: ' + ' · '.join(f'PC{i+1} = {v:+.4f}' for i,v in enumerate(score)) + '\n', 'muted')
                    self.detail.insert('end', 'Computed from standardized valence, direction, and intensity. PCA details shows axis weights.\n', 'muted')
                else:self.detail.insert('end','No PCA coordinate: unknown direction or insufficient varying data.\n','muted')
            elif r['direction'] is not None:
                self.detail.insert('end', f"Plot coordinates: X (valence) = {r['valence']:+.2f}; Y (direction) = {r['direction']:+.2f}; Z (intensity) = {r['intensity']:.2f}.\n", 'muted')
            else:
                self.detail.insert('end', 'Not plotted: the model did not assign a directional coordinate.\n', 'muted')
        start=self.detail.index('end-1c')
        text=self.paragraphs[index-1]
        self.detail.insert('end',text+'\n\n')
        if r:
            for e in r['emotions']:
                for evidence in e['evidence']:
                    quote=evidence['quote'];offset=text.find(quote)
                    for word in evidence['signal_words']:
                        word_offset=quote.find(word)
                        if offset>=0 and word_offset>=0:
                            a=offset+word_offset
                            self.detail.tag_add('signal',f'{start}+{a}c',f'{start}+{a+len(word)}c')
            self.detail.insert('end',r['summary']+'\n')
            self.detail.insert('end',f"Uncertainty: {r['uncertainty']}. {r['uncertainty_note']}\n",'muted')
            for e in r['emotions']:
                self.detail.insert('end',e['label'].capitalize()+'\n','heading')
                self.detail.insert('end',f"Experiencer: {e['experiencer']}  ·  Target / focus: {e['target'] or 'unspecified'}\n",'muted')
                self.detail.insert('end',f"Intensity {number(e['intensity'])}  ·  Valence {number(e['valence'],True)}  ·  Direction {number(e['direction'],True)}\n",'muted')
                self.detail.insert('end',e['explanation']+'\n')
                for evidence in e['evidence']:
                    self.detail.insert('end','“'+evidence['quote']+'”\n','quote')
                    self.detail.insert('end','Signals: '+', '.join(evidence['signal_words'])+'\n','muted')
                    self.detail.insert('end',evidence['explanation']+'\n')
        else:self.detail.insert('end',self.reviews.get(index,'This paragraph has not been analyzed.'),'muted')
        self.detail.configure(state='disabled')

    def save_session(self):
        if not self.paragraphs:messagebox.showinfo('Nothing to save','Analyze some text first.');return
        path=filedialog.asksaveasfilename(defaultextension='.json',initialfile='emotion-atlas-session.json',filetypes=[('Atlas session','*.json')])
        if path:
            try:
                Path(path).write_text(json.dumps(export_session(self.paragraphs,self.results,self.title_text,self.usage,self.reviews),ensure_ascii=False,indent=2),encoding='utf-8')
                self.dirty=False;self.status.set('Session saved with source text and evidence. API key was not saved.')
            except OSError as e:messagebox.showerror('Save failed',str(e))

    def open_session(self):
        if not self.confirm_replace():return
        path=filedialog.askopenfilename(filetypes=[('Atlas session','*.json')])
        if not path:return
        try:
            data=json.loads(Path(path).read_text(encoding='utf-8'));paragraphs,results=load_session(data)
            self.mode.set('Blank lines');self.set_source('\n\n'.join(paragraphs),str(data.get('title','Imported session')))
            self.results=results
            reviews=data.get('reviews',{})
            self.reviews={int(k):v for k,v in reviews.items() if isinstance(k,str) and k.isdigit() and 1<=int(k)<=len(paragraphs) and int(k) not in results and isinstance(v,str)} if isinstance(reviews,dict) else {}
            usage=data.get('usage',{})
            self.usage={k:usage.get(k,0) if type(usage.get(k,0)) is int and usage.get(k,0)>=0 else 0 for k in ('input_tokens','output_tokens')}
            self.current_id=next(iter(results),None);self.refresh();self.dirty=False
            self.status.set('Session restored. Enter your API key to resume unfinished paragraphs.')
        except (OSError,ValueError,AnalysisError) as e:messagebox.showerror('Cannot open session',str(e))

    def save_csv(self):
        if not self.results:messagebox.showinfo('No results','Analyze some paragraphs first.');return
        path=filedialog.asksaveasfilename(defaultextension='.csv',initialfile='emotion-atlas-scores.csv',filetypes=[('CSV','*.csv')])
        if path:
            try:
                with open(path,'w',encoding='utf-8-sig',newline='') as f:
                    w=csv.writer(f);w.writerow(['paragraph','intensity','valence','direction','direction_status','tone','uncertainty','emotions','summary','text','model'])
                    for i,r in sorted(self.results.items()):
                        row=[i,r['intensity'],r['valence'],r['direction'],r['direction_status'],r['tone'],r['uncertainty'],', '.join(e['label'] for e in r['emotions']),r['summary'],self.paragraphs[i-1],MODEL]
                        # Protect imported spreadsheet cells from formula interpretation.
                        w.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v for v in row])
                self.status.set('Paragraph scores exported to CSV. Save a session for full evidence and resuming.')
            except OSError as e:messagebox.showerror('Export failed',str(e))

    def method(self):
        messagebox.showinfo('About the analysis',
            'GPT-6 Luna infers emotional meaning from each paragraph and nearby context.\n\n'
            'Intensity: 0 absent → 1 extreme strength of feeling.\n'
            'Valence: −1 unpleasant → +1 pleasant. Opposing feelings can balance valence without lowering intensity.\n'
            'Direction: −1 internal/self-focused → +1 directed toward others or the world. Unclear direction is not plotted.\n\n'
            'Each result decomposes emotions into experiencer, target/focus, scores, and verbatim evidence. '
            'These are interpretive estimates, not validated psychological measurements or a diagnosis. '
            'Uncertainty is a model judgment, not a calibrated probability.\n\n'
            'Paragraphs are sent in batches of up to 6, with up to 1,200 characters of neighboring context per side. '
            'There is no whole-book memory. The key stays in memory; API requests use store=false. '
            'OpenAI API data policies still apply.\n\n'
            'Open any UTF-8 .txt file or paste your own text to begin.',parent=self)

    def close(self):
        if self.running:
            if not messagebox.askyesno('Analysis is running','Quit now? Completed unsaved results will be lost. The in-flight API request may still incur usage.'):return
        elif self.dirty:
            if not messagebox.askyesno('Unsaved results','Quit without saving the current session?'):return
        self.pause_playback()
        self.cancel.set();self.key.set('');self.destroy()


if __name__=='__main__':
    import sys
    if len(sys.argv)==3 and sys.argv[1]=='--smoke-test':
        from smoke import run_smoke_test
        run_smoke_test(Atlas,Path(sys.argv[2]))
    else:
        Atlas().mainloop()
