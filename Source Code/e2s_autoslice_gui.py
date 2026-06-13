#!/usr/bin/env python3
_n='output'
_m='geometry'
_l='__done__'
_k='--suffix='
_j='Choose an output folder.'
_i='Missing input'
_h='WAV files'
_g='Stem split (demucs)'
_f='Sensitivity'
_e='horizontal'
_d='Browse'
_c='Remove'
_b='Add folder'
_a='Add files'
_Z='extended'
_Y='Chop tool'
_X='Manual'
_W='last_out_dir'
_V='last_in_dir'
_U='Open Electribe2 Sampler Loop Utility'
_T='utf-8'
_S='normal'
_R='*.*'
_Q='All files'
_P='Append to filename'
_O='Output folder'
_N='bold'
_M='all'
_L='disabled'
_K='nsew'
_J=False
_I='x'
_H='e'
_G=True
_F='h2'
_E='ew'
_D=None
_C='body'
_B='end'
_A='w'
import json,os,queue,sys,threading,traceback,tkinter as tk
from tkinter import ttk,filedialog,messagebox
import e2s_sample_all as e2s,e2s_autoslice,e2s_chop
from VerticalScrolledFrame import VerticalScrolledFrame
try:from PIL import Image,ImageTk;_HAVE_PIL=_G
except Exception:_HAVE_PIL=_J
try:from tkinterdnd2 import TkinterDnD,DND_FILES;_HAVE_DND=_G;_BASE=TkinterDnD.Tk
except Exception:_HAVE_DND=_J;_BASE=tk.Tk
CATEGORIES=list(e2s.esli_str_to_OSC_cat)
BEATS=list(e2s.esli_beat)
MODES='transient','hybrid','grid'
FORMAT_LABELS=[('wav','esli'),('e2sSample.all',_M)]
FORMAT_LABEL_TO_VALUE=dict(FORMAT_LABELS)
SENSITIVITY_RANGE=1.,15.,8.
TOLERANCE_RANGE=.0,1.,.35
FONT_FAMILY='Helvetica'
SOUNDCLOUD_URL='https://soundcloud.com/speedsick'
CONFIG_PATH=os.path.expanduser('~/.e2s_autoslice_gui.json')
def resource_path(rel):A=getattr(sys,'_MEIPASS',os.path.dirname(os.path.abspath(__file__)));return os.path.join(A,rel)
def _load_fonts(root):
	import glob
	files=glob.glob(resource_path('fonts/*.ttf'))+glob.glob(resource_path('fonts/*.otf'))+glob.glob(resource_path('fonts/*.otb'))
	if not files:return
	if sys.platform=='darwin':
		try:
			import ctypes,ctypes.util
			ct=ctypes.cdll.LoadLibrary(ctypes.util.find_library('CoreText')or'/System/Library/Frameworks/CoreText.framework/CoreText')
			cf=ctypes.cdll.LoadLibrary(ctypes.util.find_library('CoreFoundation')or'/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
			cf.CFStringCreateWithCString.restype=ctypes.c_void_p;cf.CFStringCreateWithCString.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_uint32]
			cf.CFURLCreateWithFileSystemPath.restype=ctypes.c_void_p;cf.CFURLCreateWithFileSystemPath.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_long,ctypes.c_bool]
			ct.CTFontManagerRegisterFontsForURL.restype=ctypes.c_bool;ct.CTFontManagerRegisterFontsForURL.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p]
			for f in files:
				s=cf.CFStringCreateWithCString(None,f.encode('utf-8'),0x08000100);u=cf.CFURLCreateWithFileSystemPath(None,s,0,False)
				try:ct.CTFontManagerRegisterFontsForURL(u,1,None)
				except Exception:pass
			return
		except Exception:pass
	try:
		from tkextrafont import Font
		for f in files:
			try:Font(root,file=f)
			except Exception:pass
	except Exception:pass
class _StreamRedirect:
	def __init__(A,q):A.q=q
	def write(A,s):
		if s:A.q.put(s)
	def flush(A):0
class AutoSliceGUI(_BASE):
	def __init__(A):super().__init__();A.title(_U);A.minsize(660,640);A.log_queue=queue.Queue();A.worker=_D;A._manual_win=_D;A._chop_win=_D;A._bpm_win=_D;A._bpm_overrides={};A._action_buttons=[];A._bg_img=_D;A._bg_raw=_D;A.cfg=A._load_config();A.last_in_dir=A.cfg.get(_V,'');A.last_out_dir=A.cfg.get(_W,'');A._apply_theme();A._set_icon();A._build_menu();A._build_background();A._build_widgets();A._restore_state();A.protocol('WM_DELETE_WINDOW',A._on_close);A.after(100,A._drain_log)
	def _apply_theme(B):
		global FONT_FAMILY
		try:_load_fonts(B)
		except Exception:pass
		try:
			import tkinter.font as tkfont;C={A.lower():A for A in tkfont.families(B)};D=None
			for(E,F)in C.items():
				if 'gohu'in E:D=F;break
			if not D:
				for G in('Menlo','DejaVu Sans Mono','Consolas','Helvetica Neue','Helvetica','Arial'):
					if G.lower()in C:D=C[G.lower()];break
			if D:FONT_FAMILY=D
		except Exception:pass
		try:B.option_add('*Font',(FONT_FAMILY,13));A=ttk.Style(B);A.configure('.',font=(FONT_FAMILY,13));A.configure('TButton',font=(FONT_FAMILY,13));A.configure('TLabelframe.Label',font=(FONT_FAMILY,13,_N))
		except Exception:pass
	def _set_icon(A):
		try:B=tk.PhotoImage(file=resource_path('images/AppIcon.png'));A.iconphoto(_G,B);A._icon_ref=B
		except Exception:pass
	def _build_background(A):
		B=resource_path('steak.png')
		if not os.path.exists(B):return
		A.bg_canvas=tk.Canvas(A,highlightthickness=0,bd=0);A.bg_canvas.place(x=0,y=0,relwidth=1,relheight=1)
		try:
			if _HAVE_PIL:A._bg_raw=Image.open(B).convert('RGB')
			else:A._bg_img=tk.PhotoImage(file=B);A.bg_canvas.create_image(0,0,anchor='nw',image=A._bg_img)
		except Exception:return
		A.bg_canvas.bind('<Configure>',A._redraw_bg)
	def _redraw_bg(A,event):
		E=event
		if not(_HAVE_PIL and A._bg_raw):return
		C,D=max(1,E.width),max(1,E.height);F,G=A._bg_raw.size;H=max(C/F,D/G);B=A._bg_raw.resize((int(F*H),int(G*H)),Image.LANCZOS);I=(B.width-C)//2;J=(B.height-D)//2;B=B.crop((I,J,I+C,J+D));A._bg_img=ImageTk.PhotoImage(B);A.bg_canvas.delete(_M);A.bg_canvas.create_image(0,0,anchor='nw',image=A._bg_img)
	def _build_menu(B):A=tk.Menu(B);C=tk.Menu(A,tearoff=0);C.add_command(label='Chop sliced WAVs…',command=B._open_chop);A.add_cascade(label='Tools',menu=C);D=tk.Menu(A,tearoff=0);D.add_command(label=_X,command=B._show_manual);A.add_cascade(label='Help',menu=D);B.config(menu=A)
	def _build_widgets(A):
		S='drums';R='Loop';Q='left';L='readonly';C=dict(padx=6,pady=3);A._vpane=ttk.PanedWindow(A,orient='vertical');A._vpane.pack(fill='both',expand=True,padx=8,pady=8);A._hpane=ttk.PanedWindow(A._vpane,orient='horizontal');A._vpane.add(A._hpane,weight=3);A._panel=VerticalScrolledFrame(A._hpane);A._hpane.add(A._panel,weight=1);E=A._panel.interior;E.columnconfigure(1,weight=1);B=0;ttk.Label(E,text='Inputs (wav files / folders)').grid(row=B,column=0,columnspan=2,sticky=_A,**C);M=ttk.Frame(E);M.grid(row=B,column=2,sticky=_H,**C);ttk.Button(M,text=_Y,command=A._open_chop).pack(side=Q,padx=(0,4));ttk.Button(M,text=_X,command=A._show_manual).pack(side=Q);ttk.Button(M,text='Editor',command=A._toggle_editor).pack(side=Q,padx=(4,0));B+=1;A.inputs_list=tk.Listbox(E,height=5,selectmode=_Z);A.inputs_list.grid(row=B,column=0,columnspan=2,sticky=_K,**C);A._enable_drop(A.inputs_list,A._add_paths);I=ttk.Frame(E);I.grid(row=B,column=2,sticky='n',**C);ttk.Button(I,text=_a,command=A._add_files).pack(fill=_I,pady=2);ttk.Button(I,text=_b,command=A._add_folder).pack(fill=_I,pady=2);ttk.Button(I,text=_c,command=A._remove_selected).pack(fill=_I,pady=2);ttk.Button(I,text='Clear',command=lambda:A.inputs_list.delete(0,_B)).pack(fill=_I,pady=2);A.suffix_var=tk.StringVar();W=ttk.Frame(I);W.pack(side='top',fill=_I,pady=(10,2));ttk.Label(W,text=_P).pack(anchor=_A);ttk.Entry(W,textvariable=A.suffix_var).pack(fill=_I);E.rowconfigure(B,weight=1);B+=1
		if _HAVE_DND:ttk.Label(E,text='(tip: drag files or folders onto the list)',foreground='#555').grid(row=B,column=0,columnspan=3,sticky=_A,padx=6);B+=1
		ttk.Label(E,text=_O).grid(row=B,column=0,sticky=_A,**C);A.output_var=tk.StringVar();ttk.Entry(E,textvariable=A.output_var).grid(row=B,column=1,sticky=_E,**C);ttk.Button(E,text=_d,command=A._pick_output).grid(row=B,column=2,sticky=_E,**C);B+=1;ttk.Separator(E,orient=_e).grid(row=B,column=0,columnspan=3,sticky=_E,pady=8);B+=1;F=ttk.Frame(E);F.grid(row=B,column=0,columnspan=3,sticky=_E)
		for T in(1,3):F.columnconfigure(T,weight=1)
		D=0;A.mode_var=tk.StringVar(value=MODES[0]);A.format_var=tk.StringVar(value=FORMAT_LABELS[0][0]);ttk.Label(F,text='Mode').grid(row=D,column=0,sticky=_A,**C);ttk.Combobox(F,textvariable=A.mode_var,values=MODES,state=L,width=14).grid(row=D,column=1,sticky=_A,**C);ttk.Label(F,text='Format').grid(row=D,column=2,sticky=_A,**C);ttk.Combobox(F,textvariable=A.format_var,values=[A for(A,B)in FORMAT_LABELS],state=L,width=18).grid(row=D,column=3,sticky=_A,**C);D+=1;A.steps_var=tk.StringVar();A.bpm_var=tk.StringVar();ttk.Label(F,text='Steps (blank = auto)').grid(row=D,column=0,sticky=_A,**C);ttk.Entry(F,textvariable=A.steps_var,width=14).grid(row=D,column=1,sticky=_A,**C);ttk.Label(F,text='BPM (blank = auto)').grid(row=D,column=2,sticky=_A,**C);ttk.Entry(F,textvariable=A.bpm_var,width=14).grid(row=D,column=3,sticky=_A,**C);D+=1;A.beat_var=tk.StringVar(value=BEATS[0]);A.category_var=tk.StringVar(value=R if R in CATEGORIES else CATEGORIES[0]);ttk.Label(F,text='Beat').grid(row=D,column=0,sticky=_A,**C);ttk.Combobox(F,textvariable=A.beat_var,values=BEATS,state=L,width=14).grid(row=D,column=1,sticky=_A,**C);ttk.Label(F,text='Category').grid(row=D,column=2,sticky=_A,**C);ttk.Combobox(F,textvariable=A.category_var,values=CATEGORIES,state=L,width=18).grid(row=D,column=3,sticky=_A,**C);D+=1;A.tolerance_var=tk.DoubleVar(value=TOLERANCE_RANGE[2]);A.sensitivity_var=tk.DoubleVar(value=SENSITIVITY_RANGE[2]);ttk.Label(F,text='Tolerance (hybrid)').grid(row=D,column=0,sticky=_A,**C);A._slider(F,A.tolerance_var,TOLERANCE_RANGE,D,1);ttk.Label(F,text=_f).grid(row=D,column=2,sticky=_A,**C);A._slider(F,A.sensitivity_var,SENSITIVITY_RANGE,D,3);D+=1;A.first_slot_var=tk.StringVar(value='19');ttk.Label(F,text='First slot (bank format)').grid(row=D,column=0,sticky=_A,**C);ttk.Entry(F,textvariable=A.first_slot_var,width=14).grid(row=D,column=1,sticky=_A,**C);D+=1;H=ttk.Frame(E);H.grid(row=B+1,column=0,columnspan=3,sticky=_A,pady=(6,0));A.loop_var=tk.BooleanVar(value=_G);A.drop_silent_var=tk.BooleanVar(value=_G);A.metrics_var=tk.BooleanVar(value=_G);A.mono_var=tk.BooleanVar(value=_J);A.verbose_var=tk.BooleanVar(value=_G);ttk.Checkbutton(H,text='Set loop points',variable=A.loop_var).grid(row=0,column=0,sticky=_A,padx=6);ttk.Checkbutton(H,text='Deactivate silent steps',variable=A.drop_silent_var).grid(row=0,column=1,sticky=_A,padx=6);ttk.Checkbutton(H,text='Per-slice metrics',variable=A.metrics_var).grid(row=0,column=2,sticky=_A,padx=6);ttk.Checkbutton(H,text='Force mono',variable=A.mono_var).grid(row=1,column=0,sticky=_A,padx=6);ttk.Checkbutton(H,text='Verbose log',variable=A.verbose_var).grid(row=1,column=1,sticky=_A,padx=6);B+=2;K=ttk.LabelFrame(E,text=_g,padding=6);K.grid(row=B,column=0,columnspan=3,sticky=_E,pady=(8,0));A.demucs_var=tk.BooleanVar(value=_J);ttk.Checkbutton(K,text='Split each input into stems first, then slice the stems',variable=A.demucs_var).grid(row=0,column=0,columnspan=6,sticky=_A,padx=4);ttk.Label(K,text='Stems:').grid(row=1,column=0,sticky=_A,padx=4);A.stem_vars={}
		for(U,N)in enumerate((S,'bass','vocals','other')):O=tk.BooleanVar(value=True);A.stem_vars[N]=O;ttk.Checkbutton(K,text=N,variable=O).grid(row=1,column=1+U,sticky=_A,padx=4)
		A.stems_only_var=tk.BooleanVar(value=_J);ttk.Checkbutton(K,text='Split stems only (no slicing)',variable=A.stems_only_var).grid(row=2,column=0,columnspan=6,sticky=_A,padx=4)
		B+=1;G=ttk.Frame(E);G.grid(row=B,column=0,columnspan=3,sticky=_E,pady=(10,4));G.columnconfigure(0,weight=1);A.status_var=tk.StringVar(value='Ready.');ttk.Label(G,textvariable=A.status_var).grid(row=0,column=0,sticky=_A);ttk.Button(G,text='Copy log',command=A._copy_log).grid(row=0,column=1,sticky=_H,padx=(0,4));ttk.Button(G,text='Save log…',command=A._save_log).grid(row=0,column=2,sticky=_H,padx=(0,4));ttk.Button(G,text='Clear log',command=A._clear_log).grid(row=0,column=3,sticky=_H,padx=(0,8));ttk.Button(G,text='Detect BPM',command=A._detect_bpm).grid(row=0,column=4,sticky=_H,padx=(0,4));A.run_btn=ttk.Button(G,text='Slice',command=A._run);A.run_btn.grid(row=0,column=5,sticky=_H);A._action_buttons.append(A.run_btn);B+=1;A.progress=ttk.Progressbar(E,mode='indeterminate');A.progress.grid(row=B,column=0,columnspan=3,sticky=_E,pady=(0,6));B+=1;J=ttk.Frame(E);J.grid(row=B,column=0,columnspan=3,sticky=_K);E.rowconfigure(B,weight=2);J.rowconfigure(0,weight=1);J.columnconfigure(0,weight=1);A.log=tk.Text(J,height=10,wrap='word',state=_L,font=(FONT_FAMILY,12));A.log.grid(row=0,column=0,sticky=_K);P=ttk.Scrollbar(J,command=A.log.yview);P.grid(row=0,column=1,sticky='ns');A.log.configure(yscrollcommand=P.set);B+=1;ttk.Style().configure('Donate.TButton',font=(FONT_FAMILY,9),padding=0);V=ttk.Frame(E);V.grid(row=B,column=0,columnspan=3,sticky=_E,pady=(4,0));ttk.Button(V,text='♥ donate',width=9,style='Donate.TButton',command=A._donate).pack(side='right');ttk.Button(V,text='♫',width=3,style='Donate.TButton',command=A._soundcloud).pack(side='right',padx=(0,4))
	def _slider(I,parent,var,rng,row,col):
		A=var;E,F,J=rng;K=float(E).is_integer()and float(F).is_integer()and(F-E)>=3;D='%d'if K else'%.2f';B=ttk.Frame(parent);B.grid(row=row,column=col,sticky=_E,padx=6,pady=3);B.columnconfigure(0,weight=1);C=ttk.Label(B,width=4,anchor=_H,text=D%A.get())
		def G(v):A.set(round(float(v))if K else round(float(v),2));C.configure(text=D%A.get())
		H=ttk.Scale(B,from_=E,to=F,variable=A,orient=_e,command=G);H.grid(row=0,column=0,sticky=_E);C.grid(row=0,column=1,padx=(6,0))
	def _enable_drop(B,widget,handler):
		A=widget
		if not _HAVE_DND:return
		try:A.drop_target_register(DND_FILES);A.dnd_bind('<<Drop>>',lambda e:handler(B.tk.splitlist(e.data)))
		except Exception:pass
	def _add_paths(B,paths):
		for A in paths:
			if os.path.isdir(A)or A.lower().endswith(('.wav','.aif','.aiff','.aifc','.flac','.mp3','.m4a','.aac','.ogg','.oga','.opus','.wma','.caf','.w64')):
				B.inputs_list.insert(_B,A)
				if os.path.isdir(A):B.last_in_dir=A
				else:B.last_in_dir=os.path.dirname(A)
	def _show_manual(B):
		if B._manual_win is not _D and B._manual_win.winfo_exists():B._manual_win.lift();B._manual_win.focus_set();return
		C=tk.Toplevel(B);B._manual_win=C;C.title('Oe2sLU - Manual');C.minsize(560,480);C.geometry('660x600');D=ttk.Frame(C,padding=8);D.pack(fill='both',expand=_G);D.rowconfigure(0,weight=1);D.columnconfigure(0,weight=1);A=tk.Text(D,wrap='word',padx=10,pady=8,font=(FONT_FAMILY,13));A.grid(row=0,column=0,sticky=_K);E=ttk.Scrollbar(D,command=A.yview);E.grid(row=0,column=1,sticky='ns');A.configure(yscrollcommand=E.set);ttk.Button(D,text='Close',command=C.destroy).grid(row=1,column=0,columnspan=2,sticky=_H,pady=(8,0));A.tag_configure('h1',font=(FONT_FAMILY,17,_N),spacing1=10,spacing3=6);A.tag_configure(_F,font=(FONT_FAMILY,13,_N),spacing1=8,spacing3=3);A.tag_configure(_C,spacing3=4)
		for(F,G)in MANUAL:A.insert(_B,G+'\n',F)
		A.configure(state=_L)
	def _detect_bpm(A):
		import tkinter as tk,threading,os as _os
		files_in=list(A.inputs_list.get(0,_B))
		if not files_in:messagebox.showwarning('Missing input','Add at least one WAV file or folder.');return
		argv=list(files_in)+['--beat',A.beat_var.get()]
		s=A.steps_var.get().strip()
		if s:argv+=['--steps',s]
		if A.mono_var.get():argv+=['--mono']
		if getattr(A,'_bpm_win',_D)is not None and A._bpm_win.winfo_exists():A._bpm_win.destroy()
		if not hasattr(A,'_bpm_overrides'):A._bpm_overrides={}
		try:
			import audio as _au;HAVE_AUDIO=_au.sd is not None
		except Exception:HAVE_AUDIO=_J
		W=tk.Toplevel(A);A._bpm_win=W;W.title('Set BPM per track');W.minsize(600,360)
		O=ttk.Frame(W,padding=8);O.pack(fill='both',expand=True);O.rowconfigure(1,weight=1);O.columnconfigure(0,weight=1)
		ttk.Label(O,text='Use BPM starts at the detected tempo. Edit it, or use x2 / /2 to fix half/double-time, then Apply. Clear a box to keep the detected value.',wraplength=580,justify='left').grid(row=0,column=0,columnspan=2,sticky=_A,pady=(0,6))
		CV=tk.Canvas(O,highlightthickness=0);SB=ttk.Scrollbar(O,orient='vertical',command=CV.yview);BODY=ttk.Frame(CV)
		BODY.bind('<Configure>',lambda e:CV.configure(scrollregion=CV.bbox(_M)))
		CV.create_window((0,0),window=BODY,anchor='nw');CV.configure(yscrollcommand=SB.set)
		CV.grid(row=1,column=0,sticky=_K);SB.grid(row=1,column=1,sticky='ns')
		def wheel(e):
			d=0
			if getattr(e,'delta',0):d=-1 if e.delta>0 else 1
			elif getattr(e,'num',0)==4:d=-1
			elif getattr(e,'num',0)==5:d=1
			CV.yview_scroll(d,'units');return'break'
		for _ev in('<MouseWheel>','<Button-4>','<Button-5>'):CV.bind(_ev,wheel);BODY.bind(_ev,wheel)
		ST=tk.StringVar(value='Analyzing %d input(s)...'%len(files_in));ttk.Label(O,textvariable=ST).grid(row=2,column=0,columnspan=2,sticky=_A,pady=(6,0))
		BT=ttk.Frame(O);BT.grid(row=3,column=0,columnspan=2,sticky=_E,pady=(8,0))
		A._bpm_rows={}
		def fmt(v):
			try:return'%d'%round(float(v))
			except Exception:return''
		def cur(stem):
			R=A._bpm_rows.get(stem)
			if not R:return _D
			t=R['var'].get().strip()
			if t:
				try:return float(t)
				except ValueError:return _D
			return R['detected']
		def mul(stem,f):
			b=cur(stem)
			if b:A._bpm_rows[stem]['var'].set(fmt(b*f))
		def play(path):
			if not HAVE_AUDIO:ST.set('Audio preview unavailable (sounddevice not installed).');return
			def go():
				try:
					import audio
					from e2s_sample_import import from_wav,ImportOptions
					smp,_C2,_C3=from_wav(path,ImportOptions());snd=audio.Sound(bytes(smp.get_data().rawdata),smp.get_fmt());A.after(0,lambda:audio.player.play_start(snd))
				except Exception as e:A.after(0,lambda:ST.set('Cannot preview: %s'%e))
			threading.Thread(target=go,daemon=True).start()
		def stop():
			try:
				import audio;audio.player.play_stop()
			except Exception:pass
		def build(res):
			if not W.winfo_exists():return
			for c,txt in enumerate(('Track','Detected','','','Use BPM','')):
				ttk.Label(BODY,text=txt,font=(FONT_FAMILY,11,_N)).grid(row=0,column=c,padx=6,pady=(0,4),sticky=_A)
			r=1
			for name,bpm,bars,steps,src,dur,path in res:
				stem=_os.path.splitext(name)[0]
				var=tk.StringVar()
				pv=A._bpm_overrides.get(stem)
				var.set(fmt(pv) if pv else (fmt(bpm) if bpm else ''))
				A._bpm_rows[stem]={'detected':bpm,'var':var,'path':path}
				ttk.Label(BODY,text=name[:36],width=36,anchor=_A).grid(row=r,column=0,padx=6,pady=2,sticky=_A)
				ttk.Label(BODY,text=(('%.1f'%bpm)if bpm else '?'),width=10,anchor=_A).grid(row=r,column=1,padx=6,sticky=_A)
				ttk.Button(BODY,text='x2',width=3,command=lambda s=stem:mul(s,2.0)).grid(row=r,column=2,padx=1)
				ttk.Button(BODY,text='/2',width=3,command=lambda s=stem:mul(s,0.5)).grid(row=r,column=3,padx=1)
				sp=tk.Spinbox(BODY,from_=20,to=400,increment=1,width=7,textvariable=var);sp.grid(row=r,column=4,padx=6)
				for _ev in('<MouseWheel>','<Button-4>','<Button-5>'):sp.bind(_ev,wheel)
				pb=ttk.Button(BODY,text='▶',width=3,command=lambda p=path:play(p));pb.grid(row=r,column=5,padx=2)
				if not HAVE_AUDIO:pb.state(['disabled'])
				r+=1
			ST.set('%d track(s). Edit Use BPM if needed, then Apply.'%len(res))
		def apply():
			n=0
			for stem,R in A._bpm_rows.items():
				t=R['var'].get().strip()
				if t:
					try:A._bpm_overrides[stem]=float(t);n+=1
					except ValueError:pass
				elif stem in A._bpm_overrides:del A._bpm_overrides[stem]
			A.status_var.set(('BPM set for %d track(s).'%n) if n else 'BPM overrides cleared.');W.destroy()
		def clearov():
			A._bpm_overrides.clear()
			for R in A._bpm_rows.values():R['var'].set('')
			ST.set('Overrides cleared.')
		ttk.Button(BT,text='Stop',command=stop).pack(side='left')
		ttk.Button(BT,text='Clear all',command=clearov).pack(side='left',padx=6)
		ttk.Button(BT,text='Cancel',command=W.destroy).pack(side='right',padx=(6,0))
		ttk.Button(BT,text='Apply',command=apply).pack(side='right')
		def work():
			try:r=e2s_autoslice.detect_bpms(argv)
			except Exception as e:r=[('(error)',_D,_D,_D,str(e),0,'')]
			A.after(0,lambda:build(r))
		threading.Thread(target=work,daemon=True).start()
	def _donate(A):
		import webbrowser;webbrowser.open('https://www.paypal.com/donate/?business=777paranoia%40gmail.com&currency_code=USD')
	def _soundcloud(A):
		import webbrowser;webbrowser.open(SOUNDCLOUD_URL)
	def _toggle_editor(A):
		import tkinter as tk
		if getattr(A,'_editor_frame',None) is None:
			try:
				from Oe2sSLE_GUI import SampleAllEditor;A._editor_frame=tk.Frame(A._hpane);B=SampleAllEditor(A._editor_frame);B.pack(fill='both',expand=True);A.title(_U)
			except Exception as e:A._append_log('editor failed to load: %s\n'%e);return
		if getattr(A,'_editor_visible',False):
			A._hpane.forget(A._editor_frame);A._editor_visible=False
		else:
			A._hpane.add(A._editor_frame,weight=2);A._editor_visible=True
			try:A.geometry('1320x820')
			except Exception:pass
	def host_show_slice_editor(A,smpl_list,smpl_num):
		import tkinter as tk
		from Oe2sSLE_GUI import SliceEditor
		if getattr(A,'_slice_wrap',None) is None:
			A._slice_wrap=tk.Frame(A._vpane,borderwidth=2,relief='sunken');b=tk.Frame(A._slice_wrap);tk.Label(b,text='Slice editor').pack(side='left',padx=4);tk.Button(b,text='Close slice editor',command=A.host_hide_slice_editor).pack(side='right',padx=4,pady=2);b.pack(fill='x');A._slice_ed=SliceEditor(A._slice_wrap);A._slice_ed.pack(fill='both',expand=True)
		A._slice_ed.set_sample(smpl_list,smpl_num)
		if not getattr(A,'_slice_visible',False):A._vpane.add(A._slice_wrap,weight=2);A._slice_visible=True
		try:A.geometry('1320x920')
		except Exception:pass
	def host_hide_slice_editor(A):
		try:
			import audio;audio.player.play_stop()
		except Exception:pass
		if getattr(A,'_slice_visible',False):A._vpane.forget(A._slice_wrap);A._slice_visible=False
	def _open_chop(A):
		if A._chop_win is not _D and A._chop_win.winfo_exists():A._chop_win.lift();A._chop_win.focus_set();return
		E=tk.Toplevel(A);A._chop_win=E;E.title('Chop sliced WAVs');E.minsize(520,420);C=dict(padx=6,pady=3);B=ttk.Frame(E,padding=10);B.pack(fill='both',expand=_G);B.columnconfigure(1,weight=1);ttk.Label(B,text='Split sliced WAVs into one file per slice (reads cue/esli markers).').grid(row=0,column=0,columnspan=3,sticky=_A,**C);ttk.Label(B,text='Sliced WAVs').grid(row=1,column=0,sticky='nw',**C);A.chop_list=tk.Listbox(B,height=5,selectmode=_Z);A.chop_list.grid(row=1,column=1,sticky=_K,**C);B.rowconfigure(1,weight=1);A._enable_drop(A.chop_list,lambda ps:[A.chop_list.insert(_B,B)for B in ps if os.path.isdir(B)or B.lower().endswith('.wav')]);D=ttk.Frame(B);D.grid(row=1,column=2,sticky='n',**C);ttk.Button(D,text=_a,command=A._chop_add_files).pack(fill=_I,pady=2);ttk.Button(D,text=_b,command=A._chop_add_folder).pack(fill=_I,pady=2);ttk.Button(D,text=_c,command=lambda:[A.chop_list.delete(B)for B in reversed(A.chop_list.curselection())]).pack(fill=_I,pady=2);ttk.Button(D,text='Clear',command=lambda:A.chop_list.delete(0,_B)).pack(fill=_I,pady=2);ttk.Label(B,text=_O).grid(row=2,column=0,sticky=_A,**C);A.chop_out_var=tk.StringVar(value=A.last_out_dir);ttk.Entry(B,textvariable=A.chop_out_var).grid(row=2,column=1,sticky=_E,**C);ttk.Button(B,text=_d,command=A._chop_pick_out).grid(row=2,column=2,sticky=_E,**C);ttk.Label(B,text=_P).grid(row=3,column=0,sticky=_A,**C);A.chop_suffix_var=tk.StringVar();ttk.Entry(B,textvariable=A.chop_suffix_var).grid(row=3,column=1,sticky=_E,**C);ttk.Label(B,text='Click-free fade (ms)').grid(row=4,column=0,sticky=_A,**C);A.chop_fade_var=tk.StringVar(value='3');ttk.Entry(B,textvariable=A.chop_fade_var,width=8).grid(row=4,column=1,sticky=_A,**C);F=ttk.Frame(B);F.grid(row=5,column=0,columnspan=3,sticky=_H,pady=(8,0));G=ttk.Button(F,text='Chop',command=A._run_chop);G.pack(side='right');A._action_buttons.append(G)
	def _chop_add_files(A):
		B=filedialog.askopenfilenames(title='Select sliced WAVs',initialdir=A.last_in_dir or _D,filetypes=[(_h,'*.wav'),(_Q,_R)])
		for C in B:A.chop_list.insert(_B,C)
		if B:A.last_in_dir=os.path.dirname(B[0])
	def _chop_add_folder(A):
		B=filedialog.askdirectory(title='Select a folder',initialdir=A.last_in_dir or _D)
		if B:A.chop_list.insert(_B,B);A.last_in_dir=B
	def _chop_pick_out(A):
		B=filedialog.askdirectory(title=_O,initialdir=A.last_out_dir or _D)
		if B:A.chop_out_var.set(B);A.last_out_dir=B
	def _run_chop(A):
		D=list(A.chop_list.get(0,_B));E=A.chop_out_var.get().strip()
		if not D:messagebox.showwarning(_i,'Add at least one sliced WAV or folder.');return
		if not E:messagebox.showwarning('Missing output',_j);return
		B=list(D)+['-o',E];F=A.chop_suffix_var.get()
		if F:B+=[_k+F]
		C=A.chop_fade_var.get().strip()
		if C:
			try:float(C);B+=['--fade-ms',C]
			except ValueError:messagebox.showwarning('Bad value','Fade must be a number.');return
		G='$ e2s_chop '+' '.join(_quote(A)for A in B);A._start(lambda:e2s_chop.main(B),G,'Chopping…')
	def _add_files(A):
		B=filedialog.askopenfilenames(title='Select audio files',initialdir=A.last_in_dir or _D,filetypes=[('Audio files','*.wav *.aif *.aiff *.flac *.mp3 *.m4a *.aac *.ogg *.opus *.wma *.caf'),(_h,'*.wav'),(_Q,_R)])
		for C in B:A.inputs_list.insert(_B,C)
		if B:A.last_in_dir=os.path.dirname(B[0])
	def _add_folder(A):
		B=filedialog.askdirectory(title='Select a folder of WAV files',initialdir=A.last_in_dir or _D)
		if B:A.inputs_list.insert(_B,B);A.last_in_dir=B
	def _remove_selected(A):
		for B in reversed(A.inputs_list.curselection()):A.inputs_list.delete(B)
	def _pick_output(A):
		B=filedialog.askdirectory(title='Select output folder',initialdir=A.last_out_dir or _D)
		if B:A.output_var.set(B);A.last_out_dir=B
	def _build_argv(A):
		K='%.3f';F=list(A.inputs_list.get(0,_B))
		if not F:raise ValueError('Add at least one WAV file or folder.')
		G=A.output_var.get().strip()
		if not G:raise ValueError(_j)
		H=FORMAT_LABEL_TO_VALUE[A.format_var.get()];B=list(F);B+=['-o',G];B+=['--mode',A.mode_var.get()];B+=['--format',H];B+=['--beat',A.beat_var.get()];B+=['--category',A.category_var.get()];I=A.suffix_var.get()
		if I:B+=[_k+I]
		C=A.steps_var.get().strip()
		if C:int(C);B+=['--steps',C]
		D=A.bpm_var.get().strip()
		if D:float(D);B+=['--bpm',D]
		B+=['--tolerance',K%float(A.tolerance_var.get())];B+=['--sensitivity',K%float(A.sensitivity_var.get())]
		if H==_M:
			E=A.first_slot_var.get().strip()
			if E:int(E);B+=['--first-slot',E]
		if not A.loop_var.get():B+=['--no-loop']
		if not A.drop_silent_var.get():B+=['--keep-silent']
		if not A.metrics_var.get():B+=['--no-metrics']
		if A.mono_var.get():B+=['--mono']
		if A.verbose_var.get():B+=['-v']
		if A.stems_only_var.get()or A.demucs_var.get():
			J=[C for(C,D)in A.stem_vars.items()if D.get()]
			if not J:raise ValueError('Stem split is on but no stems are selected.')
			if A.stems_only_var.get():B+=['--stems-only','--stems',','.join(J)]
			else:B+=['--demucs','--stems',','.join(J)]
		if getattr(A,'_bpm_overrides',_D):
			import tempfile;ovd={kk:vv for(kk,vv)in A._bpm_overrides.items()if vv}
			if ovd:
				tf=tempfile.NamedTemporaryFile('w',suffix='.json',prefix='oe2s_bpm_',delete=_J);json.dump(ovd,tf);tf.close();B+=['--bpm-map',tf.name]
		return B
	def _run(A):
		try:B=A._build_argv()
		except ValueError as C:messagebox.showwarning(_i,str(C));return
		D='$ e2s_autoslice '+' '.join(_quote(A)for A in B);A._start(lambda:e2s_autoslice.main(B),D,'Slicing…')
	def _start(A,fn,banner,busy_msg):
		if A.worker and A.worker.is_alive():return
		A._clear_log();A._append_log(banner+'\n\n');A._set_busy(_G,busy_msg);A.worker=threading.Thread(target=A._worker,args=(fn,),daemon=_G);A.worker.start()
	def _worker(B,fn):
		D,E=sys.stdout,sys.stderr;sys.stdout=sys.stderr=_StreamRedirect(B.log_queue);A=1
		try:A=fn()
		except SystemExit as C:A=C.code if isinstance(C.code,int)else 1
		except Exception:traceback.print_exc();A=1
		finally:sys.stdout,sys.stderr=D,E
		B.log_queue.put((_l,A))
	def _set_busy(A,busy,msg=''):
		for B in list(A._action_buttons):
			try:B.configure(state=_L if busy else _S)
			except Exception:A._action_buttons.remove(B)
		if busy:A.status_var.set(msg);A.progress.start(12)
		else:A.progress.stop()
	def _drain_log(A):
		try:
			while _G:
				B=A.log_queue.get_nowait()
				if isinstance(B,tuple)and B and B[0]==_l:A._on_done(B[1])
				else:A._append_log(B)
		except queue.Empty:pass
		A.after(100,A._drain_log)
	def _on_done(A,rc):A._set_busy(_J);A.status_var.set('Done.'if rc==0 else'Finished with errors (see log).')
	def _append_log(A,s):A.log.configure(state=_S);A.log.insert(_B,s);A.log.see(_B);A.log.configure(state=_L)
	def _clear_log(A):A.log.configure(state=_S);A.log.delete('1.0',_B);A.log.configure(state=_L)
	def _log_text(A):return A.log.get('1.0','end-1c')
	def _copy_log(A):A.clipboard_clear();A.clipboard_append(A._log_text());A.update();A.status_var.set('Log copied to clipboard.')
	def _save_log(B):
		C=B._log_text()
		if not C.strip():messagebox.showinfo('Nothing to save','The log is empty.');return
		A=filedialog.asksaveasfilename(title='Save log',defaultextension='.txt',initialfile='e2s_autoslice_log.txt',filetypes=[('Text files','*.txt'),(_Q,_R)])
		if not A:return
		try:
			with open(A,_A,encoding=_T)as D:D.write(C)
			B.status_var.set('Log saved: '+os.path.basename(A))
		except OSError as E:messagebox.showerror('Could not save',str(E))
	def _load_config(B):
		try:
			with open(CONFIG_PATH,'r',encoding=_T)as A:return json.load(A)
		except Exception:return{}
	def _restore_state(A):
		B=A.cfg.get(_m)
		if B:
			try:A.geometry(B)
			except Exception:pass
		C=A.cfg.get(_n,'')
		if C:A.output_var.set(C)
	def _on_close(A):
		try:
			A.cfg.update({_m:A.geometry(),_n:A.output_var.get(),_V:A.last_in_dir,_W:A.last_out_dir or A.output_var.get()})
			with open(CONFIG_PATH,_A,encoding=_T)as B:json.dump(A.cfg,B,indent=2)
		except Exception:pass
		A.destroy()
MANUAL=[('h1',_U),(_C,'Batch auto-slicer for Korg electribe sampler (e2s) loops. Point it at WAV files or folders, choose how to slice, and it writes sliced samples ready for the device. All processing is offline; nothing is uploaded.'),(_F,'Quick start'),(_C,'1. Add files or a folder under Inputs (or drag them onto the list).\n2. Pick an Output folder.\n3. Leave Mode on transient and click Slice.\nThe log shows what happened and the equivalent command line.'),(_F,'Modes'),(_C,'transient (default) - detect hits/beats (spectral-flux onset detection), then lock every slice to the BPM-derived 16th-note grid: the loop is divided into whole 16ths and each hit is quantized to the grid line of the cell it falls in, so every slice is an exact number of 16ths and off-grid notes keep their timing inside their slice. Best for most loops.\ngrid - cut the loop into equal divisions (the Steps value).\nhybrid - an equal grid where each step snaps to a nearby hit if one is close; always one slice per step. Use when you want a strict step grid aligned to the groove.'),(_F,'Output format'),(_C,'wav (default) - one WAV per input carrying the Korg slice metadata plus standard smpl/cue chunks. Drag onto the device.\ne2sSample.all - a single bank file holding every processed sample, assigned to slots starting at First slot.\nOutput is capped at the e2s memory limit (26,214,396 bytes); anything that would exceed it is skipped with a note in the log. ("esli" is Korg\'s name for the embedded slice metadata.)'),(_F,_P),(_C,"Any text here is added to the end of every output file name, before .wav. E.g. '_140' turns loop.wav into loop_140.wav."),(_F,'Steps & BPM'),(_C,"Steps is the number of grid divisions/slices (max 64). Leave blank to auto-pick (bars x 16).\nBPM is used to infer bar count. Leave blank to auto-detect: first from the filename if it contains something like '140bpm', otherwise from the loop length assuming a whole number of 4/4 bars. If detection guesses wrong, type the BPM here to force it."),(_F,'Beat & Category'),(_C,"Beat sets the device's step resolution (16, 32, triplet variants). Category is the sample category shown on the electribe (Loop, Kick, Snare, etc.)."),(_F,'Tolerance (hybrid only)'),(_C,'How far a grid point may move to land on a detected hit, as a fraction of one step. 0 = never snap (pure grid). Around 0.35 is a good default.'),(_F,_f),(_C,'Onset detection for transient and hybrid modes, on the electribe firmware 1-15 scale (Sample Edit). 1 keeps only the strongest hits; 15 catches the quietest. Default 8. In transient mode the slice count is still capped to Steps.'),(_F,_g),(_C,"Optional pre-pass: each input is separated into stems (drums/bass/vocals/other) with demucs, then the ticked stems are sliced individually. All four are selected by default. The same Mode, Tolerance and Sensitivity are applied to every stem - there is no per-stem control. Outputs are named '<track>__<stem>.wav'; raw stems are kept in a '_stems' folder. Requires demucs (bundled in the standalone app); first run downloads the model."),(_F,_Y),(_C,'Tools > Chop sliced WAVs (or the Chop tool button) splits an already-sliced WAV into one file per slice, reading the cue/esli markers this app writes. Optional click-free fade applies a short fade in/out to each exported slice so there are no edge clicks.'),(_F,'Options'),(_C,"Set loop points - loop the whole sample on the device (off = one-shot).\nDeactivate silent steps - silent steps left inactive in the step map.\nPer-slice metrics - compute each slice's peak/attack for the metadata.\nForce mono - center-mix stereo inputs to mono.\nVerbose log - print a per-file summary."),(_F,'Log'),(_C,'Copy log / Save log / Clear log manage the output pane. The first line of each run is the exact command-line equivalent.')]
def _quote(a):return'"%s"'%a if' 'in a else a
def main():os.chdir(os.path.dirname(os.path.abspath(__file__)));A=AutoSliceGUI();A.mainloop()
if __name__=='__main__':main()