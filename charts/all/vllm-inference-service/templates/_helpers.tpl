{{/*
Expand the name of the chart.
*/}}
{{- define "vllm-inference-service.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "vllm-inference-service.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "vllm-inference-service.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "vllm-inference-service.labels" -}}
helm.sh/chart: {{ include "vllm-inference-service.chart" . }}
{{ include "vllm-inference-service.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "vllm-inference-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "vllm-inference-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Hugging Face repo id for snapshot_download (quantized checkpoint).
Falls back to global.model.vllm for older values files.
*/}}
{{- define "vllm-inference-service.hfRepo" -}}
{{- if .Values.global.model.hfRepo -}}
{{- .Values.global.model.hfRepo -}}
{{- else -}}
{{- .Values.global.model.vllm -}}
{{- end -}}
{{- end }}

{{/*
OpenAI API model name exposed by vLLM (--served-model-name).
Must match config_hybrid_lightning.yml llms.*.model_name.
*/}}
{{- define "vllm-inference-service.servedModelName" -}}
{{- if .Values.global.model.servedName -}}
{{- .Values.global.model.servedName -}}
{{- else -}}
{{- (split "/" .Values.global.model.vllm)._1 -}}
{{- end -}}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "vllm-inference-service.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "vllm-inference-service.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
