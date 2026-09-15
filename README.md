# Pesquisa IFP

Pesquisa pública para estudantes e estagiários de Educação Física, com administração
privada e histórico cumulativo. As planilhas de planejamento existentes foram preservadas.

## Aplicativo

- [Pesquisa pública](https://pesquisa-ifp.187.77.248.206.sslip.io/)
- [Administração](https://pesquisa-ifp.187.77.248.206.sslip.io/admin)

O código está em `pesquisa/`. A página pública apresenta o Instituto Facility PRO e
as cinco perguntas da pesquisa. Nome, e-mail e telefone são opcionais. A autorização
para contato é independente da participação.

O painel `/admin` exige senha e código de autenticador. Mostra contagens, gráficos,
evolução diária, cruzamento formação × formato, respostas completas e exportação CSV.
Filtros: período, formação, área e formato. Cada percentual indica sua base; a pergunta
de múltipla seleção pode somar mais de 100%. Os insights são cálculos determinísticos,
sem serviço de IA e sem custo de inferência.

## Persistência e segurança

- SQLite em volume persistente, transações, restrições e migração aditiva versionada.
- Repetir o mesmo envio depois de falha de conexão não cria outra resposta.
- Não há garantia de pessoas únicas: um novo formulário pode gerar outro envio.
- Resposta aberta, nome e contatos cifrados no banco; chaves fora do código e do banco.
- Sessões administrativas revogáveis, expiração absoluta, senha com scrypt e TOTP.
- CSRF, validação no servidor, limite de corpo e tentativas, CSP e cookies seguros.
- API de leitura e exportações acessíveis somente após autenticação.
- Exportação neutraliza fórmulas de planilha inseridas em respostas.
- Backup usa snapshot consistente, com verificação de integridade e retenção de 30 dias.
- Exclusão solicitada pelo titular fica registrada para ser reaplicada em restaurações.

Veja [operação](pesquisa/OPERACAO.md) e [verificação](pesquisa/VERIFICACAO.md).
