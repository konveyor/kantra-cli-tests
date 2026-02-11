{{/*
Create the name of the service account to use
*/}}
{{- define "hello-spring-cloud.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default .Values.manifest.name .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "hello-spring-cloud.registry" -}}image-registry.openshift-image-registry.svc:5000/{{ .Release.Namespace }}/{{- end -}}

{{/*
Returns the executable name from a command string.
Example: "./tr-server" -> "tr-server"
Example: "bundle exec run-authenticator" -> "run-authenticator"
*/}}
{{- define "hello-spring-cloud.executableName" -}}
{{- $command := . | trim -}}
{{- $parts := splitList " " $command -}}
{{- $lastPart := last $parts -}}
{{- if regexMatch `\..*` $lastPart -}}
{{- regexFind `[^/]+$` $lastPart -}}
{{- else -}}
{{- $lastPart -}}
{{- end -}}
{{- end -}}

{{- define "hello-spring-cloud.quoteIfNotString" }}
{{- $value := . -}}
{{- if not (kindOf $value | eq "string") -}}
"{{- toString $value -}}"
{{- else -}}
{{- $value -}}
{{- end -}}
{{- end -}}

{{- define "hello-spring-cloud.command.parse" -}}
{{- $commandLine := . -}}
{{- $words := splitList " " $commandLine -}}
{{- $isShellCommand := false -}}

{{- range list "&&" "||" "|" ">" "<" ";" "$" -}}
{{- if contains . $commandLine -}}
{{- $isShellCommand = true -}}
{{- end -}}
{{- end -}}

{{- if $isShellCommand -}}
command:
  - "/bin/bash"
args:
  - "-c"
  - |
    {{ $commandLine }}
{{- else -}}
{{- $args := rest $words -}}
command:
  - {{ first $words | quote }}
{{ $args := rest $words -}}
{{- if $args -}}
args:
{{- range $args }}
  - {{ . | quote }}
{{- end }}
{{- end -}}
{{- end -}}
{{- end -}}
