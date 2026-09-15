'use strict';
const form = document.querySelector('#survey');
const steps = [...form.querySelectorAll('[data-step]')];
const err = document.querySelector('#form-error');
let step = 0;
const titles = ['Sua formação', 'Seu caminho', 'Sua preparação', 'Como quer aprender', 'Sua experiência', 'Seus dados'];
const lastStep = steps.length - 1;
let submitting = false;
form.noValidate = true;
function showStep(focus = false) {
  steps.forEach(el => { el.hidden = Number(el.dataset.step) !== step; });
  document.querySelector('#previous').hidden = step === 0;
  document.querySelector('#next').hidden = step === lastStep;
  document.querySelector('#submit').hidden = step !== lastStep;
  document.querySelector('#step-label').textContent = step < 5 ? `Pergunta ${step + 1} de 5` : 'Última etapa';
  document.querySelector('#step-title').textContent = titles[step];
  const progress = document.querySelector('#progress');
  progress.value = step + 1;
  progress.setAttribute('aria-valuetext', `Etapa ${step + 1} de ${steps.length}`);
  err.hidden = true;
  if (focus) {
    const target = steps[step].querySelector('legend,h2');
    target.tabIndex = -1;
    target.focus({preventScroll: true});
    document.querySelector('.survey-card').scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start'});
  }
}
function error(message) { err.textContent = message; err.hidden = false; }
function validStep() {
  for (const container of steps.filter(el => !el.hidden)) {
    for (const input of container.querySelectorAll('input,textarea')) {
      if (!input.checkValidity()) { input.reportValidity(); return false; }
    }
  }
  if (step === 2 && !form.querySelector('input[name="gaps"]:checked')) {
    error('Na pergunta 3, selecione uma ou duas opções.');
    form.querySelector('input[name="gaps"]').focus();
    return false;
  }
  return true;
}
document.querySelector('#next').addEventListener('click', () => { if (validStep()) { step++; showStep(true); } });
document.querySelector('#previous').addEventListener('click', () => { step--; showStep(true); });
form.querySelectorAll('[name="gaps"]').forEach(input => input.addEventListener('change', () => {
  const others = [...form.querySelectorAll('[name="gaps"]')].filter(x => x !== input);
  if (input.checked && input.value === 'all') others.forEach(x => { x.checked = false; });
  else if (input.checked) form.querySelector('[name="gaps"][value="all"]').checked = false;
  const checked = form.querySelectorAll('[name="gaps"]:checked');
  if (checked.length > 2) { input.checked = false; error('Você pode selecionar até duas opções.'); }
  else err.hidden = true;
}));
document.querySelector('#wish').addEventListener('input', e => { document.querySelector('#characters').textContent = e.target.value.length.toLocaleString('pt-BR'); });
const privacy = document.querySelector('#privacy-dialog');
document.querySelector('#open-privacy').addEventListener('click', () => privacy.showModal());
document.querySelector('#close-privacy').addEventListener('click', () => privacy.close());
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (submitting) return;
  if (step < lastStep) { if (validStep()) { step++; showStep(true); } return; }
  if (!validStep()) return;
  const fields = new FormData(form);
  const body = Object.fromEntries(fields);
  body.gaps = fields.getAll('gaps');
  body.contact_consent = fields.has('contact_consent');
  body.research_consent = fields.has('research_consent');
  body.form_token = form.dataset.token;
  body.submission_key = form.dataset.key;
  if (body.contact_consent && !body.email.trim() && !body.phone.trim()) {
    error('Informe e-mail ou telefone para receber contato, ou desmarque a autorização.'); return;
  }
  const button = document.querySelector('#submit');
  submitting = true;
  form.querySelectorAll('.form-actions button').forEach(control => { control.disabled = true; });
  button.textContent = 'Registrando…'; err.hidden = true;
  try {
    const response = await fetch('/api/responses', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content}, body: JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível registrar. Tente novamente.');
    document.querySelector('#receipt').textContent = data.id;
    form.hidden = true;
    document.querySelector('.form-top').hidden = true;
    document.querySelector('#progress').hidden = true;
    const success = document.querySelector('#success'); success.hidden = false; success.focus();
  } catch (failure) {
    error(failure instanceof TypeError ? 'A conexão falhou. Suas respostas continuam nesta tela. Tente enviar novamente; o mesmo envio não será duplicado.' : failure.message);
  } finally {
    submitting = false;
    form.querySelectorAll('.form-actions button').forEach(control => { control.disabled = false; });
    button.textContent = 'Enviar respostas';
  }
});
showStep();
