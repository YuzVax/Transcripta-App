param([string]$ReferenceDir='',[string]$OutDir=(Join-Path (Split-Path $PSScriptRoot -Parent) 'dist'))
$ErrorActionPreference='Stop'
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$Build=Join-Path $PSScriptRoot 'build'
$payload=Join-Path $Build 'payload.zip';$hashFile=Join-Path $Build 'sha256.txt'
$tree=[Microsoft.CodeAnalysis.CSharp.CSharpSyntaxTree]::ParseText([IO.File]::ReadAllText((Join-Path $PSScriptRoot 'Launcher.cs')))
$refs=[Collections.Generic.List[Microsoft.CodeAnalysis.MetadataReference]]::new()
foreach($name in @('mscorlib.dll','System.dll','System.Core.dll','System.IO.Compression.dll','System.Windows.Forms.dll','System.Drawing.dll')){$refs.Add([Microsoft.CodeAnalysis.MetadataReference]::CreateFromFile((Join-Path $ReferenceDir $name)))}
$opts=[Microsoft.CodeAnalysis.CSharp.CSharpCompilationOptions]::new([Microsoft.CodeAnalysis.OutputKind]::WindowsApplication).WithOptimizationLevel([Microsoft.CodeAnalysis.OptimizationLevel]::Release).WithPlatform([Microsoft.CodeAnalysis.Platform]::X64).WithDeterministic($true)
$comp=[Microsoft.CodeAnalysis.CSharp.CSharpCompilation]::Create('Transcripta_v2',[Microsoft.CodeAnalysis.SyntaxTree[]]@($tree),$refs,$opts)
$resources=[Collections.Generic.List[Microsoft.CodeAnalysis.ResourceDescription]]::new()
$resources.Add([Microsoft.CodeAnalysis.ResourceDescription]::new('payload.zip',[Func[IO.Stream]]{[IO.File]::OpenRead($payload)},$true))
$resources.Add([Microsoft.CodeAnalysis.ResourceDescription]::new('sha256.txt',[Func[IO.Stream]]{[IO.File]::OpenRead($hashFile)},$true))
$iconPath=Join-Path (Split-Path $PSScriptRoot -Parent) 'assets/logo.ico'
$resources.Add([Microsoft.CodeAnalysis.ResourceDescription]::new('logo.ico',[Func[IO.Stream]]{[IO.File]::OpenRead($iconPath)},$true))
$logoPng=Join-Path (Split-Path $PSScriptRoot -Parent) 'assets/logo.png'
$resources.Add([Microsoft.CodeAnalysis.ResourceDescription]::new('logo.png',[Func[IO.Stream]]{[IO.File]::OpenRead($logoPng)},$true))
$wordmark=Join-Path (Split-Path $PSScriptRoot -Parent) 'assets/wordmark.png'
$resources.Add([Microsoft.CodeAnalysis.ResourceDescription]::new('wordmark.png',[Func[IO.Stream]]{[IO.File]::OpenRead($wordmark)},$true))
$manifest=[IO.File]::OpenRead((Join-Path $PSScriptRoot 'app.manifest'));$icon=[IO.File]::OpenRead($iconPath)
# Identical native PE icon path to OptimiZation: one RT_GROUP_ICON (32512),
# backed by every frame of assets/logo.ico; not merely a managed resource.
$win32=$comp.CreateDefaultWin32Resources($true,$false,$manifest,$icon)
$exe=Join-Path $OutDir 'Transcripta_v2.exe';$stream=[IO.File]::Open($exe,[IO.FileMode]::Create)
try{
    $result=$comp.Emit($stream,$null,$null,$win32,$resources,$null,[Threading.CancellationToken]::None)
    $result.Diagnostics | ForEach-Object {Write-Output $_.ToString()}
    if(-not $result.Success){throw 'Compilación fallida.'}
}finally{$stream.Dispose();$win32.Dispose();$icon.Dispose();$manifest.Dispose()}
Write-Output "PE generado: $exe"
