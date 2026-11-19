export function ColorModeScript() {
  const script = `(function(){try{var k='chakra-ui-color-mode';var t=localStorage.getItem(k)||'light';var r=document.documentElement;r.classList.add(t);r.style.colorScheme=t;}catch(e){}})();`;
  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
