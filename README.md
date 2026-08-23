# 🃏 Binder — Monitor de Preços Pokémon TCG

Monitoramento automático de preços de boxes, combos e cards avulsos de
Pokémon TCG, comparando múltiplos sites (BR e internacional) com
histórico e gráficos de variação — 100% grátis, sem servidor.

![status](https://img.shields.io/badge/status-ativo-brightgreen)
![licença](https://img.shields.io/badge/licença-MIT-blue)
![Python](https://img.shields.io/badge/Python-3.12-yellow)

Roda inteiramente com contas gratuitas do GitHub:
- **GitHub Actions** executa o scraper todo dia, de graça, e salva o
  resultado como um arquivo (`docs/data.json`) direto no repositório —
  fazendo as vezes de "banco de dados".
- **GitHub Pages** hospeda o painel (`docs/index.html`), de graça, lendo
  esse arquivo.

Sem VPS, sem cartão de crédito, sem custo — dentro dos limites generosos
do plano grátis do GitHub (2.000 minutos de Actions/mês em repositório
privado, ilimitado se o repositório for público).

## Passo a passo

### 1. Criar o repositório no GitHub
1. Entre em [github.com/new](https://github.com/new)
2. Dê um nome (ex: `pokemon-tcg-monitor`) e crie o repositório **público**
   (privado também funciona, só consome minutos do plano grátis)

### 2. Subir estes arquivos
No seu computador, dentro da pasta extraída deste zip:
```bash
git init
git add .
git commit -m "Monitor de preços Pokémon TCG"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/SEU-REPOSITORIO.git
git push -u origin main
```

### 3. Ativar o GitHub Pages
1. No repositório, vá em **Settings → Pages**
2. Em "Source", escolha **Deploy from a branch**
3. Branch: **main**, pasta: **/docs**
4. Salvar. Em 1-2 minutos seu site fica no ar em
   `https://SEU-USUARIO.github.io/SEU-REPOSITORIO/`

### 4. Rodar a primeira busca (sem esperar o agendamento)
1. No repositório, vá na aba **Actions**
2. Clique no workflow **"Atualizar preços Pokémon TCG"**
3. Clique em **"Run workflow"** → **Run workflow** de novo pra confirmar
4. Espere terminar (1-2 minutos) — ele já commita o `docs/data.json`
   atualizado sozinho
5. Atualize a página do seu site (pode levar 1-2 min pro Pages
   republicar) e os dados devem aparecer

### 5. Deixar rodando sozinho
Não precisa fazer mais nada — o workflow já está agendado pra rodar
**a cada 1 hora, todo dia**, automaticamente, graças ao
`.github/workflows/scrape.yml`.

### 6. Adicionar/editar produtos
Edite `products.json` direto pelo site do GitHub (ou no seu computador
+ `git push`). Não precisa mexer em nenhum outro arquivo.

Pra cards avulsos, preencha `"card_number"` (ex: `"199/165"`) — o script
só aceita um preço se esse número aparecer no título do resultado
encontrado.

## Limitações honestas

- Sem banco de dados de verdade — o histórico cresce como um arquivo
  JSON dentro do repositório. Pra uso pessoal (dezenas/centenas de
  produtos, anos de histórico) isso é tranquilo; se crescer demais
  (milhares de produtos), valeria migrar pra um banco de verdade.
- Sites com proteção anti-bot forte (Amazon, principalmente) podem
  bloquear o GitHub Actions — os servidores do GitHub às vezes são
  reconhecidos e bloqueados com mais facilidade que uma conexão residencial.
- Sites que carregam preço via JavaScript não são lidos por este scraper
  simples.
- Busca por nome pode ocasionalmente casar com o produto errado — confira
  o campo `matchedUrl` dentro do `docs/data.json` de vez em quando.
- Respeite o robots.txt e os termos de uso de cada site.
