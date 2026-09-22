// Resolves the backend origin. Served by Flask: same origin (''). Hosted build (e.g. Vercel):
// NAZAR_API_DEFAULT points at the local backend; override with ?api=http://host:port (remembered).
(()=>{
  const hosted=typeof window.NAZAR_API_DEFAULT==='string';
  let base=hosted?window.NAZAR_API_DEFAULT:'';
  if(hosted){try{const q=new URLSearchParams(location.search).get('api');if(q!==null)localStorage.setItem('nazar-api',q);base=localStorage.getItem('nazar-api')||base}catch(error){}}
  base=base.replace(/\/+$/,'');
  window.NAZAR_API=base;
  window.nazarUrl=(path)=>typeof path==='string'&&path.startsWith('/')?base+path:path;
})();
