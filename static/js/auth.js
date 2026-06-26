(function () {
  var form = document.getElementById('login-form');
  if (!form) return;
  form.addEventListener('submit', function () {
    var btn = document.getElementById('login-btn');
    document.getElementById('login-icon').classList.add('d-none');
    document.getElementById('login-spinner').classList.remove('d-none');
    document.getElementById('login-label').textContent = ' Iniciando…';
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    btn.setAttribute('aria-label', 'Iniciando sesión…');
  });
}());
