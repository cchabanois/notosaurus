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
			// Three kinds of pages: what is the same everywhere, the Android app's own, the add-on's
			// own (and standalone's). A common page shows a difference in <Tabs syncKey="mode">
			// (labels: "Android app" / "Computer"; fr: "Application Android" / "Ordinateur"), so the
			// reader's choice follows from page to page. Slugs stay flat: the app and the add-on link
			// to some of them.
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
					items: [{ slug: 'which-notosaurus' }],
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
						{ slug: 'cards-in-anki' },
						{ slug: 'several-children' },
					],
				},
				{
					label: 'Android app',
					translations: {
						fr: 'Application Android',
						es: 'Aplicación Android',
						de: 'Android-App',
						it: 'App Android',
						'pt-BR': 'App Android',
					},
					items: [
						{ slug: 'android-app' },
						{ slug: 'app-subscription' },
						{ slug: 'app-ankidroid' },
						{ slug: 'app-with-computer' },
						{ slug: 'app-settings' },
						{ slug: 'app-troubleshooting' },
						{ slug: 'app-privacy' },
					],
				},
				{
					label: 'Anki add-on',
					translations: {
						fr: 'Greffon Anki',
						es: 'Complemento de Anki',
						de: 'Anki-Add-on',
						it: 'Add-on di Anki',
						'pt-BR': 'Complemento do Anki',
					},
					items: [
						{ slug: 'getting-started' },
						{ slug: 'phone' },
						{ slug: 'ai-services' },
						{ slug: 'send-to-anki' },
						{ slug: 'in-anki' },
						{ slug: 'troubleshooting' },
						{ slug: 'privacy' },
						{ slug: 'install' },
					],
				},
				{
					label: 'Help',
					translations: { fr: 'Aide', es: 'Ayuda', de: 'Hilfe', it: 'Aiuto', 'pt-BR': 'Ajuda' },
					items: [{ slug: 'faq' }, { slug: 'whats-new' }],
				},
			],
		}),
	],
});
