<template>
  <div v-if="visible && certification" class="modal d-block" tabindex="-1" style="background: rgba(0, 0, 0, 0.6)">
    <div class="modal-dialog modal-dialog-centered">
      <div class="modal-content shadow-lg">
        <div class="modal-header bg-success text-white">
          <h5 class="modal-title">
            <i class="bi bi-qr-code me-2"></i>Etiqueta Física de Mantenimiento (AD-08)
          </h5>
          <button type="button" class="btn-close btn-close-white" @click="$emit('close')"></button>
        </div>
        <div class="modal-body d-flex flex-column align-items-center">
          <div id="printable-sticker" class="border border-2 border-dark rounded p-3 bg-white w-100" style="max-width: 360px">
            <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-2">
              <div>
                <div class="fw-bold text-uppercase small text-primary">BioTrack CMMS</div>
                <div class="fw-bold fs-6">VERIFICACIÓN METROLÓGICA</div>
              </div>
              <span class="badge bg-success fs-6">VIGENTE</span>
            </div>

            <div class="row g-2 align-items-center">
              <div class="col-7 small">
                <div><strong>Folio:</strong> {{ certification.folio_biotrack }}</div>
                <div><strong>Activo:</strong> {{ asset?.inventory_code }}</div>
                <div><strong>Serie:</strong> {{ asset?.serial_number }}</div>
                <div><strong>Últ. Servicio:</strong> {{ certification.service_date }}</div>
                <div><strong>Próx. Vigencia:</strong> {{ certification.expiration_date }}</div>
                <div v-if="certification.external_lab_folio" class="text-muted">
                  <strong>Lab Ext:</strong> {{ certification.external_lab_folio }}
                </div>
              </div>
              <div class="col-5 text-center">
                <img
                  :src="`/api/v1/public/sticker/${certification.public_qr_token}/qr.svg`"
                  alt="QR de verificación pública"
                  class="img-fluid border p-1 bg-white"
                  style="max-width: 120px"
                />
                <div class="text-muted" style="font-size: 0.65rem">Consulta pública</div>
              </div>
            </div>

            <div class="border-top mt-2 pt-1 text-muted" style="font-size: 0.68rem">
              Doble validación: {{ certification.biomedical_signer_name }} + {{ certification.area_receiver_name || 'Pendiente' }}
            </div>
          </div>

          <div class="mt-3 text-center small">
            <router-link
              :to="`/verify/${certification.public_qr_token}`"
              target="_blank"
              class="btn btn-outline-primary btn-sm me-2"
            >
              <i class="bi bi-box-arrow-up-right me-1"></i>Abrir Consulta Pública QR
            </router-link>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline-secondary" @click="$emit('close')">Cerrar</button>
          <button class="btn btn-success" @click="printSticker">
            <i class="bi bi-printer-fill me-1"></i>Imprimir
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  visible: Boolean,
  certification: Object,
  asset: Object,
})
defineEmits(['close'])

function printSticker() {
  window.print()
}
</script>
