# Registra el agente SEO de Cassoni en el Programador de tareas de Windows.
# Corre de lunes a viernes, cada hora de 9 a 17 (el agente respeta el cupo de 10
# fichas por día, así que correrlo varias veces es seguro).
#
#   En seco (por defecto):            .\scripts\instalar_tarea_windows.ps1
#   Escribiendo en la tienda:         .\scripts\instalar_tarea_windows.ps1 -Escribir
#   Quitar la tarea:                  Unregister-ScheduledTask -TaskName "Cassoni Agente SEO" -Confirm:$false
#
# La computadora tiene que estar prendida en ese horario. Para que corra siempre,
# conviene instalarlo en un servidor (ver docs/OPERACION.md, sección Cron).
param([switch]$Escribir)

$raiz = Split-Path -Parent $PSScriptRoot
$python = Join-Path $raiz ".venv-win\Scripts\python.exe"
$script = Join-Path $raiz "tools\agente_diario.py"
$args = "`"$script`""
if ($Escribir) { $args += " --write" }

$accion = New-ScheduledTaskAction -Execute $python -Argument $args -WorkingDirectory $raiz
$dias = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
$disparos = foreach ($h in 9..17) {
    New-ScheduledTaskTrigger -Weekly -DaysOfWeek $dias -At ("{0:D2}:05" -f $h)
}
$opciones = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "Cassoni Agente SEO" -Action $accion -Trigger $disparos `
    -Settings $opciones -Description "Agente SEO de fichas de cassoni.com (reglas del SEO + DeepSeek)" -Force
Write-Host "Tarea registrada. Reportes en evidencia\diario\ y logs en logs\."
