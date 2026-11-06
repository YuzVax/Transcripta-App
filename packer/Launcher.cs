// Transcripta — YuzVax. Session-local, hash-verified Windows launcher.
using System;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Runtime.InteropServices;
using System.Threading;
using System.Collections.Generic;
using System.Drawing;
using System.Windows.Forms;
[assembly: AssemblyTitle("Transcripta")]
[assembly: AssemblyDescription("Transcripción y traducción local. Edición portátil CPU.")]
[assembly: AssemblyProduct("Transcripta")]
[assembly: AssemblyCompany("YuzVax")]
[assembly: AssemblyCopyright("Copyright © 2026 YuzVax")]
[assembly: AssemblyVersion("1.1.10.0")]
[assembly: AssemblyFileVersion("1.1.10.0")]
internal static class Launcher {
    const string AppId = "YuzVax.Transcripta.v1";
    const string Marker = ".transcripta-session";
    static readonly string Root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Transcripta");
    [DllImport("shell32.dll",CharSet=CharSet.Unicode)] static extern int SetCurrentProcessExplicitAppUserModelID(string id);
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr CreateJobObject(IntPtr attr,string name);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool SetInformationJobObject(IntPtr h,int cls,ref JobLimits data,uint len);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool AssignProcessToJobObject(IntPtr job,IntPtr process);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool TerminateJobObject(IntPtr job,uint code);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    [DllImport("uxtheme.dll",CharSet=CharSet.Unicode)] static extern int SetWindowTheme(IntPtr h,string app,string id);
    [DllImport("gdi32.dll")] static extern IntPtr CreateRoundRectRgn(int l,int t,int r,int b,int w,int h);
    [DllImport("dwmapi.dll")] static extern int DwmSetWindowAttribute(IntPtr hwnd,int attr,ref int value,int size);
    [StructLayout(LayoutKind.Sequential)] struct BasicLimits { public long PerProcess,PerJob;public uint Flags;public UIntPtr Min,Max;public uint Active;public UIntPtr Affinity;public uint Priority,Scheduling; }
    [StructLayout(LayoutKind.Sequential)] struct IoCounters {public ulong ReadOps,WriteOps,OtherOps,ReadBytes,WriteBytes,OtherBytes;}
    [StructLayout(LayoutKind.Sequential)] struct JobLimits {public BasicLimits Basic;public IoCounters IO;public UIntPtr ProcessMemory,JobMemory,PeakProcess,PeakJob;}
    static IntPtr NewJob() {
        IntPtr h=CreateJobObject(IntPtr.Zero,null); if(h==IntPtr.Zero)throw new IOException("No se pudo crear la sesión protegida.");
        var limits=new JobLimits();limits.Basic.Flags=0x2000; // KILL_ON_JOB_CLOSE
        if(!SetInformationJobObject(h,9,ref limits,(uint)Marshal.SizeOf(typeof(JobLimits)))){CloseHandle(h);throw new IOException("Windows no permite proteger los procesos de esta sesión.");}
        return h;
    }
    static void Notice(string text,bool error=false) {MessageBox.Show(text,"Transcripta",MessageBoxButtons.OK,error?MessageBoxIcon.Error:MessageBoxIcon.Information);}
    static bool IsLink(string p) {return (File.GetAttributes(p)&FileAttributes.ReparsePoint)!=0;}
    static void NormalDir(string p) {Directory.CreateDirectory(p);if(IsLink(p))throw new IOException("No se utiliza una carpeta temporal que sea un enlace: "+p);}
    static string Hash(Stream s) {using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(s)).Replace("-","").ToLowerInvariant();}
    static Dictionary<string,string> Expected() {
        var result=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);
        using(var s=Assembly.GetExecutingAssembly().GetManifestResourceStream("sha256.txt"))using(var r=new StreamReader(s)) {
            string line;while((line=r.ReadLine())!=null){int n=line.IndexOf("  ",StringComparison.Ordinal);if(n!=64)throw new IOException("Índice de integridad no válido.");result.Add(line.Substring(n+2),line.Substring(0,n));}
        }return result;
    }
    static string SafePath(string dir,string entry) {
        if(String.IsNullOrEmpty(entry)||entry.IndexOf('\\')>=0||entry.IndexOf(':')>=0||entry.StartsWith("/"))throw new IOException("Ruta del recurso no válida.");
        string[] parts=entry.Split('/');foreach(string part in parts)if(part.Length==0||part=="."||part==".."||part.EndsWith(".")||part.EndsWith(" "))throw new IOException("Ruta del recurso no válida.");
        string path=Path.GetFullPath(Path.Combine(dir,entry.Replace('/',Path.DirectorySeparatorChar)));
        if(!path.StartsWith(Path.GetFullPath(dir)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new IOException("Ruta fuera de la sesión.");
        string parent=dir;for(int i=0;i<parts.Length-1;i++){parent=Path.Combine(parent,parts[i]);NormalDir(parent);}return path;
    }
    static void Extract(string dir,ProgressBar progress) {
        var expected=Expected();var seen=new HashSet<string>(StringComparer.OrdinalIgnoreCase);int count=0;
        using(var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))using(var zip=new ZipArchive(stream,ZipArchiveMode.Read)) {
            foreach(var e in zip.Entries) {
                if(!expected.ContainsKey(e.FullName)||!seen.Add(e.FullName))throw new IOException("Recurso no reconocido o duplicado.");
                string path=SafePath(dir,e.FullName);
                using(var source=e.Open())using(var target=new FileStream(path,FileMode.CreateNew,FileAccess.Write,FileShare.None))source.CopyTo(target);
                using(var source=File.OpenRead(path))if(Hash(source)!=expected[e.FullName])throw new IOException("Recurso dañado: "+e.FullName);
                count++;if(count%40==0){progress.Value=Math.Min(100,(int)(100L*count/expected.Count));progress.Invalidate();Application.DoEvents();}
            }
        }if(count!=expected.Count)throw new IOException("Faltan archivos en el ejecutable.");progress.Value=100;progress.Invalidate();Application.DoEvents();
    }
    static void DeleteTree(string dir) {
        if(!Directory.Exists(dir))return;if(IsLink(dir))throw new IOException("No se elimina un enlace.");
        foreach(string f in Directory.GetFiles(dir)){if(IsLink(f))throw new IOException("Archivo enlazado.");File.SetAttributes(f,FileAttributes.Normal);File.Delete(f);}
        foreach(string child in Directory.GetDirectories(dir))DeleteTree(child);
        Directory.Delete(dir,false);
    }
    static bool Clean(string dir) {for(int i=0;i<20;i++){try{DeleteTree(dir);return true;}catch{Thread.Sleep(500);}}return !Directory.Exists(dir);}
    static void RemoveEmptyRoot() {try{if(Directory.Exists(Root)&&!IsLink(Root)&&Directory.GetFileSystemEntries(Root).Length==0)Directory.Delete(Root);}catch{}}
    static string ProcessStamp(Process p) {return p.Id+" "+p.StartTime.ToUniversalTime().Ticks;}
    static bool IsAlive(string stamp) {
        string[] parts=stamp.Split(' ');int pid;long ticks;
        if(parts.Length!=2||!Int32.TryParse(parts[0],out pid)||!Int64.TryParse(parts[1],out ticks))return true;
        try{using(var p=Process.GetProcessById(pid))return !p.HasExited&&p.StartTime.ToUniversalTime().Ticks==ticks;}catch(ArgumentException){return false;}catch{return true;}
    }
    static void CleanOldSessions() {
        foreach(string dir in Directory.GetDirectories(Root,"sesion-*"))try {
            string marker=Path.Combine(dir,Marker);if(IsLink(dir)||!File.Exists(marker)||IsLink(marker))continue;
            string[] stamps=File.ReadAllLines(marker);if(stamps.Length==0)continue;bool alive=false;
            foreach(string stamp in stamps)if(IsAlive(stamp)){alive=true;break;}
            if(!alive)Clean(dir); // Never stop or delete another live session.
        }catch{}
    }
    static void FolderEnv(ProcessStartInfo info,string key,string directory) {NormalDir(directory);info.EnvironmentVariables[key]=directory;}
    static ProcessStartInfo ChildInfo(string dir,string[] args) {
        string runtime=Path.Combine(dir,"python");
        var info=new ProcessStartInfo(Path.Combine(runtime,"pythonw.exe"),"-B \""+Path.Combine(dir,"bootstrap.py")+"\""+(Array.IndexOf(args,"--self-test")>=0?" --self-test":""));
        info.UseShellExecute=false;info.CreateNoWindow=true;info.WorkingDirectory=dir;
        info.EnvironmentVariables.Remove("PYTHONHOME");info.EnvironmentVariables.Remove("PYTHONPATH");
        info.EnvironmentVariables["TRANSCRIPTA_ROOT"]=dir;info.EnvironmentVariables["TRANSCRIPTA_CPU_ONLY"]="1";
        // Carpetas reales del usuario (USERPROFILE se conserva sin cambios).
        string realDocs=Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
        string realDesktop=Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
        string realProfile=Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        if(String.IsNullOrEmpty(realDocs))realDocs=realProfile;
        if(String.IsNullOrEmpty(realDesktop))realDesktop=realProfile;
        info.EnvironmentVariables["TRANSCRIPTA_USER_DOCUMENTS"]=realDocs??"";
        info.EnvironmentVariables["TRANSCRIPTA_USER_DESKTOP"]=realDesktop??"";
        info.EnvironmentVariables["TRANSCRIPTA_USER_PROFILE"]=realProfile??"";
        info.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"]="1";info.EnvironmentVariables["PYTHONNOUSERSITE"]="1";
        info.EnvironmentVariables["PYTHONUTF8"]="1";
        string cache=Path.Combine(dir,"cache");
        FolderEnv(info,"TEMP",Path.Combine(dir,"temp"));FolderEnv(info,"TMP",Path.Combine(dir,"temp"));FolderEnv(info,"TMPDIR",Path.Combine(dir,"temp"));
        // No redirigir USERPROFILE: el diálogo de archivos de Windows falla con un perfil vacío.
        // Las cachés van a la sesión vía HF_*/TEMP/APPDATA abajo.
        FolderEnv(info,"APPDATA",Path.Combine(dir,"profile","Roaming"));FolderEnv(info,"LOCALAPPDATA",Path.Combine(dir,"profile","Local"));
        FolderEnv(info,"XDG_CACHE_HOME",cache);FolderEnv(info,"XDG_DATA_HOME",Path.Combine(dir,"data"));FolderEnv(info,"XDG_CONFIG_HOME",Path.Combine(dir,"config"));
        FolderEnv(info,"HF_HOME",Path.Combine(cache,"huggingface"));FolderEnv(info,"HF_HUB_CACHE",Path.Combine(cache,"huggingface","hub"));
        FolderEnv(info,"HUGGINGFACE_HUB_CACHE",Path.Combine(cache,"huggingface","hub"));FolderEnv(info,"HF_ASSETS_CACHE",Path.Combine(cache,"huggingface","assets"));
        FolderEnv(info,"HF_XET_CACHE",Path.Combine(cache,"huggingface","xet"));FolderEnv(info,"HF_DATASETS_CACHE",Path.Combine(cache,"huggingface","datasets"));
        info.EnvironmentVariables["HF_TOKEN_PATH"]=Path.Combine(cache,"huggingface","token");
        info.EnvironmentVariables["HF_HUB_DISABLE_TELEMETRY"]="1";info.EnvironmentVariables["HF_HUB_DISABLE_SYMLINKS_WARNING"]="1";info.EnvironmentVariables["DO_NOT_TRACK"]="1";
        FolderEnv(info,"ARGOS_PACKAGES_DIR",Path.Combine(dir,"data","argos-translate","packages"));
        FolderEnv(info,"ARGOS_TRANSLATE_PACKAGE_DIR",Path.Combine(dir,"data","argos-translate","packages"));
        FolderEnv(info,"ARGOS_CACHE_DIR",Path.Combine(cache,"argos-translate"));FolderEnv(info,"ARGOS_DATA_DIR",Path.Combine(dir,"data","argos-translate"));
        info.EnvironmentVariables["ARGOS_DEVICE_TYPE"]="cpu";info.EnvironmentVariables["ARGOS_COMPUTE_TYPE"]="int8";info.EnvironmentVariables["ARGOS_CHUNK_TYPE"]="MINISBD";
        FolderEnv(info,"STANZA_RESOURCES_DIR",Path.Combine(cache,"stanza"));FolderEnv(info,"TORCH_HOME",Path.Combine(cache,"torch"));
        FolderEnv(info,"PIP_CACHE_DIR",Path.Combine(cache,"pip"));FolderEnv(info,"MPLCONFIGDIR",Path.Combine(cache,"matplotlib"));
        info.EnvironmentVariables["TCL_LIBRARY"]=Path.Combine(runtime,"tcl","tcl8.6");info.EnvironmentVariables["TK_LIBRARY"]=Path.Combine(runtime,"tcl","tk8.6");
        info.EnvironmentVariables["PATH"]=Path.Combine(dir,"ffmpeg","bin")+";"+runtime+";"+Environment.GetEnvironmentVariable("PATH");
        return info;
    }
    // Splash: tarjeta gris sólida redondeada, sin borde negro (mismo lenguaje oscuro/naranja).
    static readonly Color Bg=Color.FromArgb(0x0B,0x0E,0x14);
    static readonly Color Card=Color.FromArgb(0x1A,0x1F,0x28); // gris total de la tarjeta splash
    static readonly Color TextMain=Color.FromArgb(0xE8,0xEA,0xED);
    static readonly Color Muted=Color.FromArgb(0x92,0x9C,0xAB);
    static readonly Color Accent=Color.FromArgb(0xFF,0x8C,0x00);
    static Image LoadSplashWordmark() {
        // Prefer the pre-composed T+ranscripta PNG (tight kerning baked in).
        foreach(string name in new string[]{"wordmark.png","logo.png"}) {
            using(var s=Assembly.GetExecutingAssembly().GetManifestResourceStream(name)) {
                if(s==null) continue;
                using(var tmp=Image.FromStream(s)) using(var bmp=new Bitmap(tmp)) {
                    int l=bmp.Width,t=bmp.Height,r=-1,b=-1;
                    for(int y=0;y<bmp.Height;y++) for(int x=0;x<bmp.Width;x++)
                        if(bmp.GetPixel(x,y).A>10) {l=Math.Min(l,x);t=Math.Min(t,y);r=Math.Max(r,x);b=Math.Max(b,y);}
                    if(r>=l) return bmp.Clone(new Rectangle(l,t,r-l+1,b-t+1),System.Drawing.Imaging.PixelFormat.Format32bppArgb);
                    return new Bitmap(bmp);
                }
            }
        }
        using(var s=Assembly.GetExecutingAssembly().GetManifestResourceStream("logo.ico")) {
            if(s==null) return null;
            using(var icon=new Icon(s,48,48)) return icon.ToBitmap();
        }
    }
    // Owner painting makes orange/gray deterministic: native themes can ignore
    // ProgressBar.ForeColor and otherwise reintroduce a blue/white control.
    sealed class BrandProgressBar : ProgressBar {
        public BrandProgressBar() {
            SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer,true);
        }
        protected override void OnPaint(PaintEventArgs e) {
            e.Graphics.Clear(BackColor);
            int width=Maximum>Minimum ? (int)(ClientSize.Width*(double)(Value-Minimum)/(Maximum-Minimum)) : 0;
            using(var brush=new SolidBrush(ForeColor)) e.Graphics.FillRectangle(brush,0,0,width,ClientSize.Height);
        }
    }
    static Form Splash(out ProgressBar progress) {
        var f=new Form();
        f.Text="v1.1.10"; // Solo versión; sin nombre ni icono en barra (borde none).
        f.StartPosition=FormStartPosition.CenterScreen;
        f.ClientSize=new Size(420,150);
        f.FormBorderStyle=FormBorderStyle.None;
        f.ControlBox=false;
        f.ShowInTaskbar=true;
        f.BackColor=Card; // Tarjeta gris sólida; sin marco negro exterior.
        f.ForeColor=TextMain;
        f.Font=new Font("Segoe UI",10f);
        // Esquinas bien redondeadas (sin borde pintado).
        try { f.Region=Region.FromHrgn(CreateRoundRectRgn(0,0,f.Width+1,f.Height+1,22,22)); } catch {}
        // Wordmark compuesto (T+ranscripta). Sin icono de título nativo.
        var mark=LoadSplashWordmark();
        if(mark!=null) {
            int markH=36; int markW=Math.Max(1,(int)Math.Round(markH*(double)mark.Width/mark.Height));
            var pic=new PictureBox();
            pic.Image=mark;pic.SizeMode=PictureBoxSizeMode.Zoom;
            pic.SetBounds(22,26,markW,markH);pic.BackColor=Color.Transparent;
            f.Controls.Add(pic);
        } else {
            var title=new Label();
            title.Text="Transcripta";title.Font=new Font("Segoe UI Semibold",18f,FontStyle.Bold);
            title.ForeColor=TextMain;title.BackColor=Color.Transparent;title.AutoSize=true;
            title.Location=new Point(22,32);f.Controls.Add(title);
        }
        var status=new Label();
        status.Text="Preparando Transcripta…";status.Font=new Font("Segoe UI",10f);
        status.ForeColor=Muted;status.BackColor=Color.Transparent;status.AutoSize=true;
        status.Location=new Point(22,78);f.Controls.Add(status);
        progress=new BrandProgressBar();
        progress.SetBounds(22,110, f.ClientSize.Width-44, 14);
        progress.Style=ProgressBarStyle.Continuous;progress.Minimum=0;progress.Maximum=100;progress.Value=0;
        f.Controls.Add(progress);
        f.Show();Application.DoEvents();
        try {
            SetWindowTheme(progress.Handle,"","");
            progress.ForeColor=Accent;progress.BackColor=Color.FromArgb(0x30,0x37,0x44);
        } catch {}
        try {
            int dark=1; DwmSetWindowAttribute(f.Handle,20,ref dark,4);
            // COLORREF BGR del gris de tarjeta #1A1F28
            int bg=0x00281F1A; DwmSetWindowAttribute(f.Handle,34,ref bg,4); DwmSetWindowAttribute(f.Handle,35,ref bg,4);
        } catch {}
        Application.DoEvents();
        return f;
    }

    static void KillOtherInstances() {
        // Solo cierra otros lanzadores Transcripta. El Job Object (KILL_ON_JOB_CLOSE)
        // termina a los hijos; no enumeramos pythonw ni escribimos scripts.
        int self=Process.GetCurrentProcess().Id;
        // Support both filenames during the transition to the v2 portable EXE.
        foreach(string name in new string[]{"Transcripta","Transcripta_v2"})
        foreach(Process p in Process.GetProcessesByName(name)) {
            try {
                if(p.Id==self) continue;
                try { p.Kill(); p.WaitForExit(8000); }
                catch {}
            } finally { try { p.Dispose(); } catch {} }
        }
    }

    [STAThread] static int Main(string[] args) {
        string dir=null;Mutex mutex=null;bool owned=false;IntPtr job=IntPtr.Zero;Process child=null;Form splash=null;
        try {
            if(Environment.OSVersion.Platform!=PlatformID.Win32NT)return 2;
            if(!Environment.Is64BitOperatingSystem){Notice("Transcripta necesita Windows 10/11 de 64 bits.",true);return 2;}
            AppContext.SetSwitch("Switch.System.IO.UseLegacyPathHandling",false);
            AppContext.SetSwitch("Switch.System.IO.BlockLongPaths",false);
            SetCurrentProcessExplicitAppUserModelID(AppId);Application.EnableVisualStyles();
            mutex=new Mutex(false,"Local\\"+AppId+"."+WindowsIdentity.GetCurrent().User.Value);
            try{owned=mutex.WaitOne(0);}catch(AbandonedMutexException){owned=true;}
            if(!owned){
                // Nueva instancia: cierra a la fuerza la anterior y continúa.
                KillOtherInstances();
                try{owned=mutex.WaitOne(8000);}catch(AbandonedMutexException){owned=true;}
                if(!owned){Notice("No se pudo tomar el control de Transcripta. Inténtalo de nuevo.",true);return 1;}
            }
            NormalDir(Root);CleanOldSessions();
            dir=Path.Combine(Root,"sesion-"+Process.GetCurrentProcess().Id+"-"+Guid.NewGuid().ToString("N"));NormalDir(dir);
            string ownStamp=ProcessStamp(Process.GetCurrentProcess());File.WriteAllText(Path.Combine(dir,Marker),ownStamp+Environment.NewLine);
            ProgressBar progress;splash=Splash(out progress);Extract(dir,progress);
            var info=ChildInfo(dir,args);job=NewJob();child=Process.Start(info);
            if(!AssignProcessToJobObject(job,child.Handle)){try{child.Kill();child.WaitForExit();}catch{}throw new IOException("No se pudo proteger el proceso de Transcripta.");}
            File.WriteAllLines(Path.Combine(dir,Marker),new string[]{ownStamp,ProcessStamp(child)});
            splash.Dispose();splash=null;child.WaitForExit();return child.ExitCode;
        }catch(Exception ex){if(splash!=null){splash.Dispose();splash=null;}Notice("No se pudo iniciar Transcripta.\n\n"+ex.Message,true);return 1;}
        finally {
            if(splash!=null)splash.Dispose();
            if(job!=IntPtr.Zero){TerminateJobObject(job,0);CloseHandle(job);}
            if(child!=null)child.Dispose();
            if(dir!=null&&!Clean(dir))Notice("Windows mantiene un archivo temporal ocupado. Se volverá a limpiar en el próximo inicio:\n"+dir);
            RemoveEmptyRoot();if(owned&&mutex!=null)mutex.ReleaseMutex();if(mutex!=null)mutex.Dispose();
        }
    }
}
