$A = "C:\Users\PARAS ARORA\Desktop\edit\edit\animations"
$slots = if ($args.Count) { $args } else { "slot_hook","slot_timeline","slot_glass","slot_workflow","slot_reels","slot_doc_back","slot_doc_front","slot_cta","slot_end" }
foreach ($s in $slots) {
  Set-Location "$A\$s"
  $t0 = Get-Date
  npx --yes hyperframes@0.8.111 render . --format webm --fps 25 --workers 1 --quality looks -o render.webm 2>&1 | Out-Null
  $d = ffprobe -v error -show_entries format=duration -of csv=p=0 render.webm 2>$null
  "$s done dur=$d in $([int]((Get-Date)-$t0).TotalSeconds)s"
}
"ALL DONE"
