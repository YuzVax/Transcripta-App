// Read-only visual harness: calls the actual private Splash without extraction.
using System;
using System.Reflection;
using System.Drawing;
using System.Drawing.Imaging;
using System.Windows.Forms;
using System.Threading;
internal static class PreviewSplash {
 [STAThread] static int Main(string[] args) {
  Application.EnableVisualStyles();
  var asm=Assembly.LoadFrom(args[0]);
  var method=asm.GetType("Launcher").GetMethod("Splash",BindingFlags.NonPublic|BindingFlags.Static);
  object[] values={null};
  using(var form=(Form)method.Invoke(null,values)) {
   ((ProgressBar)values[0]).Value=72;((ProgressBar)values[0]).Invalidate();
   Application.DoEvents();Thread.Sleep(150);Application.DoEvents();
   using(var bmp=new Bitmap(form.Width,form.Height)) {
    using(var g=Graphics.FromImage(bmp)) g.CopyFromScreen(form.Location,Point.Empty,form.Size);
    bmp.Save(args[1],ImageFormat.Png);
   }
  }
  return 0;
 }
}
