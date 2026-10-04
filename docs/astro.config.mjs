// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// Published on GitHub Pages: https://cchabanois.github.io/notosaurus/
export default defineConfig({
	site: 'https://cchabanois.github.io',
	base: '/notosaurus',
	integrations: [
		starlight({
			title: 'Notosaurus',
			description: 'Snap a lesson, get Anki cards.',
			logo: { src: './src/assets/logo-mark.webp' },
			favicon: '/favicon.png',
			customCss: ['./src/styles/notosaurus.css'],
			// The picture shown when the site's address is shared (from docs/demo/og-image.html)
			head: [
				{ tag: 'meta', attrs: { property: 'og:image', content: 'https://cchabanois.github.io/notosaurus/og.jpg' } },
				{ tag: 'meta', attrs: { property: 'og:image:width', content: '1200' } },
				{ tag: 'meta', attrs: { property: 'og:image:height', content: '630' } },
				{ tag: 'meta', attrs: { name: 'twitter:card', content: 'summary_large_image' } },
			],
			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/cchabanois/notosaurus' },
				{ icon: 'heart', label: 'Ko-fi', href: 'https://ko-fi.com/notosaurus' },
			],
			editLink: { baseUrl: 'https://github.com/cchabanois/notosaurus/edit/main/docs/' },
			// English at the root (/notosaurus/), the other languages under their code.
			// A page not translated yet shows the English one, with a notice.
			defaultLocale: 'root',
			locales: {
				root: { label: 'English', lang: 'en' },
				fr: { label: 'Français' },
				es: { label: 'Español' },
				de: { label: 'Deutsch' },
				it: { label: 'Italiano' },
				'pt-br': { label: 'Português (Brasil)', lang: 'pt-BR' },
			},
			sidebar: [
				{
					label: 'Start here',
					translations: {
						fr: 'Pour commencer',
						es: 'Para empezar',
						de: 'Erste Schritte',
						it: 'Per iniziare',
						'pt-BR': 'Para começar',
					},
					items: [{ slug: 'getting-started' }, { slug: 'phone' }],
				},
				{
					label: 'Using Notosaurus',
					translations: {
						fr: 'Utiliser Notosaurus',
						es: 'Usar Notosaurus',
						de: 'Notosaurus verwenden',
						it: 'Usare Notosaurus',
						'pt-BR': 'Usar o Notosaurus',
					},
					items: [
						{ slug: 'photos' },
						{ slug: 'instructions' },
						{ slug: 'review' },
						{ slug: 'lessons' },
						{ slug: 'voices' },
						{ slug: 'card-types' },
						{ slug: 'send-to-anki' },
						{ slug: 'in-anki' },
					],
				},
				{
					label: 'Guides',
					translations: { fr: 'Guides', es: 'Guías', de: 'Anleitungen', it: 'Guide', 'pt-BR': 'Guias' },
					items: [{ slug: 'several-children' }, { slug: 'ai-services' }, { slug: 'privacy' }],
				},
				{
					label: 'Help',
					translations: { fr: 'Aide', es: 'Ayuda', de: 'Hilfe', it: 'Aiuto', 'pt-BR': 'Ajuda' },
					items: [{ slug: 'faq' }, { slug: 'install' }, { slug: 'whats-new' }],
				},
			],
		}),
	],
});
