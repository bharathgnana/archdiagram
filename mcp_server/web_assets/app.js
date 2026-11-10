import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js';
import { getAuth, onAuthStateChanged, sendSignInLinkToEmail, isSignInWithEmailLink, signInWithEmailLink, signOut } from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js';

const $ = id => document.getElementById(id);
const example = {title:'Order approval',direction:'LR',nodes:[{id:'start',shape:'start',label:'Start'},{id:'submit',shape:'process',label:'Submit order'},{id:'review',shape:'decision',label:'Approved?'},{id:'end',shape:'end',label:'Complete'}],edges:[{source:'start',target:'submit'},{source:'submit',target:'review'},{source:'review',target:'end',label:'Yes'}]};
$('spec').value = JSON.stringify(example, null, 2);
$('example').onclick = () => { $('spec').value = JSON.stringify(example, null, 2); };
let auth, downloadUrl, billingConfig, billingAccount;
const status = (id, message) => { $(id).textContent = message; };
function explain(error) {
  const messages = {'auth/unauthorized-domain':'This domain is not authorized for sign-in. Contact the service administrator.', 'auth/operation-not-allowed':'Email link sign-in has not been enabled yet.', 'auth/invalid-action-code':'This sign-in link has expired or was already used. Request a new one.', 'auth/invalid-email':'Enter a valid email address.', 'auth/too-many-requests':'Too many attempts. Please try again later.'};
  return messages[error.code] || 'Unable to complete sign-in. Please try again or contact the service administrator.';
}
try {
  const response = await fetch('/api/browser-config', {cache:'no-store'});
  const config = await response.json();
  if (!config.apiKey || !config.authDomain || !config.projectId) throw new Error('not-configured');
  auth = getAuth(initializeApp(config));
  if (isSignInWithEmailLink(auth, location.href)) {
    let email = localStorage.getItem('archdiagram-signin-email');
    if (!email) email = window.prompt('Confirm the email address that received this sign-in link:');
    if (email) {
      try { await signInWithEmailLink(auth, email.trim(), location.href); localStorage.removeItem('archdiagram-signin-email'); history.replaceState({}, '', '/'); }
      catch (error) { status('login-message', explain(error)); }
    } else { status('login-message', 'Enter your email to finish sign-in, or request a new link.'); }
  }
  onAuthStateChanged(auth, async user => {
    const signedIn = Boolean(user && user.emailVerified);
    $('login').hidden = signedIn; $('studio').hidden = !signedIn; $('logout').hidden = !signedIn; $('account').hidden = !signedIn;
    $('account').textContent = signedIn ? user.email : '';
    $('issued-key').value = ''; $('new-key').hidden = true;
    if (!signedIn) { $('api-key').value = ''; billingAccount = null; }
    else await refreshBilling();
  });
} catch (error) {
  $('send-link').disabled = true;
  status('login-message', 'Email sign-in is not configured yet. Please check back soon.');
}
$('login-form').onsubmit = async event => {
  event.preventDefault(); if (!auth) return;
  const email = $('email').value.trim(); $('send-link').disabled = true;
  try { await sendSignInLinkToEmail(auth, email, {url: location.origin + '/', handleCodeInApp:true}); localStorage.setItem('archdiagram-signin-email', email); status('login-message', 'Check your inbox for a sign-in link.'); }
  catch (error) { status('login-message', explain(error)); }
  finally { $('send-link').disabled = false; }
};

async function billingRequest(path, method = 'GET') {
  if (!auth?.currentUser?.emailVerified) throw Error('Please sign in first.');
  const response = await fetch('/api/billing/' + path, {method, cache:'no-store',
    headers:{'X-Firebase-Token':await auth.currentUser.getIdToken()}});
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'Unable to contact the billing service.');
  return result;
}
function billingButtons(busy = false) {
  const enabled = Boolean(billingConfig?.enabled);
  const subscribed = billingAccount && !['none','created','authenticated','cancelled','completed','expired'].includes(billingAccount.status);
  $('subscribe').disabled = busy || !enabled || Boolean(subscribed) || Boolean(billingAccount?.active);
  $('refresh-billing').disabled = busy || !enabled;
  $('issue-key').disabled = busy || !billingAccount?.active;
  $('issue-key').textContent = billingAccount?.hasKey ? 'Replace API key' : 'Create API key';
  $('cancel-subscription').hidden = !subscribed || Boolean(billingAccount?.cancellationRequested);
  $('cancel-subscription').disabled = busy;
}
async function refreshBilling() {
  billingButtons(true);
  try {
    const response = await fetch('/api/billing/config', {cache:'no-store'});
    if (!response.ok) throw Error('Unable to check payment availability. Refresh to try again.');
    billingConfig = await response.json();
    if (!billingConfig.enabled) {
      status('billing-summary', 'Payments are not available yet. Please check back soon.');
      return;
    }
    const price = new Intl.NumberFormat(undefined, {style:'currency', currency:billingConfig.currency}).format(billingConfig.amount / 100);
    $('plan-price').textContent = price + ' / month';
    $('subscribe').textContent = 'Subscribe for ' + price + '/month';
    const user = auth.currentUser;
    const account = await billingRequest('status');
    if (auth.currentUser !== user) return;
    billingAccount = account;
    const through = account.paidThrough ? new Date(account.paidThrough * 1000).toLocaleDateString() : '';
    status('billing-summary', (billingConfig.testMode ? 'Test payments. ' : '') +
      (account.active ? `${account.cancellationRequested ? 'Renewal cancelled. ' : ''}Paid access through ${through}. ${account.usageCount} of ${account.monthlyLimit} requests used this month.` :
       `No confirmed paid access. ${price}/month includes ${billingConfig.monthlyLimit} requests. Renews monthly for up to ${billingConfig.totalCycles} cycles; cancel renewal here.`));
    status('billing-message', '');
  } catch (error) { status('billing-message', error.message); }
  finally { billingButtons(); }
}
$('refresh-billing').onclick = refreshBilling;
$('subscribe').onclick = async () => {
  billingButtons(true);
  try { const result = await billingRequest('checkout', 'POST'); location.assign(result.checkoutUrl); }
  catch (error) { status('billing-message', error.message); billingButtons(); }
};
$('issue-key').onclick = async () => {
  if (billingAccount?.hasKey && !window.confirm('Replace your API key? Your previous key will stop working immediately.')) return;
  billingButtons(true);
  try {
    const user = auth.currentUser;
    const result = await billingRequest('key', 'POST');
    if (auth.currentUser !== user) return;
    $('issued-key').value = result.apiKey; $('api-key').value = result.apiKey; $('new-key').hidden = false;
    billingAccount.hasKey = true;
    status('billing-message', 'API key created. Save it in your agent’s secret settings now.');
  } catch (error) { status('billing-message', error.message); }
  finally { billingButtons(); }
};
$('copy-key').onclick = async () => {
  try { await navigator.clipboard.writeText($('issued-key').value); status('billing-message', 'API key copied.'); }
  catch { status('billing-message', 'Clipboard access was denied. Select and copy the key manually.'); $('issued-key').type = 'text'; $('issued-key').select(); }
};
$('cancel-subscription').onclick = async () => {
  if (!window.confirm('Cancel monthly renewal? Your paid access will continue until the end of its paid period.')) return;
  billingButtons(true);
  try { const result = await billingRequest('cancel', 'POST'); await refreshBilling(); status('billing-message', result.message); }
  catch (error) { status('billing-message', error.message); }
  finally { billingButtons(); }
};
window.addEventListener('pagehide', () => { $('issued-key').value = ''; $('api-key').value = ''; });
$('logout').onclick = async () => {
  $('api-key').value = ''; $('preview-frame').removeAttribute('src'); $('preview-frame').hidden = true;
  $('empty-preview').hidden = false; $('download').disabled = true;
  if (downloadUrl) { URL.revokeObjectURL(downloadUrl); downloadUrl = null; }
  await signOut(auth);
};
$('render').onclick = async () => {
  if (!auth?.currentUser?.emailVerified) return status('render-message', 'Please sign in first.');
  let spec; try { spec = JSON.parse($('spec').value); if (!spec || Array.isArray(spec) || typeof spec !== 'object') throw Error(); } catch { return status('render-message', 'Enter a valid JSON object.'); }
  const key = $('api-key').value.trim(); if (!key) return status('render-message', 'Enter your buyer API key to render.');
  const format = $('format').value; $('render').disabled = true; status('render-message', 'Rendering…');
  try {
    const idToken = await auth.currentUser.getIdToken();
    const response = await fetch('/api/render', {method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer ' + key,'X-Firebase-Token':idToken},body:JSON.stringify({spec,format})});
    if (!response.ok) { const data = await response.json().catch(() => ({})); throw Error(data.error || `Request failed (${response.status}).`); }
    const result = await response.json();
    if (!result.ok) throw Error((result.errors || ['Could not render the diagram.']).join(' '));
    const bytes = result.content_base64 ? Uint8Array.from(atob(result.content_base64), c => c.charCodeAt(0)) : result.content;
    if (!bytes) throw Error('The service returned no diagram content.');
    if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    downloadUrl = URL.createObjectURL(new Blob([bytes], {type:result.mime_type || 'application/octet-stream'}));
    $('download').disabled = false; $('download').onclick = () => { const a = document.createElement('a'); a.href = downloadUrl; a.download = 'diagram.' + format; a.click(); };
    $('preview-frame').hidden = format !== 'svg'; $('empty-preview').hidden = format === 'svg';
    if (format === 'svg') $('preview-frame').src = downloadUrl;
    else $('empty-preview').querySelector('p').textContent = 'Your file is ready. Use Download to save it.';
    status('render-message', 'Diagram ready.' + (result.warnings?.length ? ' ' + result.warnings.join(' ') : ''));
  } catch (error) { status('render-message', error.message || 'Unable to render.'); }
  finally { $('render').disabled = false; }
};
