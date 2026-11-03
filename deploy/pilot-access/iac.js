/* Display identity only. Never modify inputs, links, API data or cryptographic code. */
(() => {
  const title = 'Votación Centro de Padres IAC';
  let queued = false;
  const observer = new MutationObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; render(); });
  });
  function render() {
    observer.disconnect();
    if (document.body) {
      if (!document.getElementById('iac-identity')) {
        const banner = document.createElement('header');
        banner.id = 'iac-identity';
        banner.innerHTML = '<span class="iac-mark" aria-hidden="true">CPA</span><div><strong>Votación Centro de Padres IAC</strong><small>Instituto Abdón Cifuentes</small><a href="/_pilot/informacion-tecnica.html" target="_blank" rel="noopener noreferrer">Información técnica y licencias</a></div><span class="iac-demo">Demostración no vinculante</span>';
        document.body.prepend(banner);
      }
      const nodes = [];
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
          if (node.parentElement?.closest('script,style,textarea,input,pre,code,label,button,option,select,.question,.answer,[role="radio"],[data-iac-preserve]')) return NodeFilter.FILTER_REJECT;
          return /\bBelenios\b/i.test(node.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
        },
      });
      while (walker.nextNode()) nodes.push(walker.currentNode);
      for (const node of nodes) node.nodeValue = node.nodeValue.replace(/\bBelenios\b/gi, 'plataforma de votación');
      for (const image of document.querySelectorAll('img[alt*="belenios" i]')) {
        image.src = '/_pilot/iac.svg';
        image.alt = 'Votación CPA IAC';
      }
    }
    if (document.title !== title) document.title = title;
    observer.observe(document.documentElement, {childList:true,subtree:true,characterData:true});
  }
  render();
})();
