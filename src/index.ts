import { Client, EmbedBuilder, TextChannel } from 'discord.js';
import { deployCommands } from './deploy';
import { commands } from './commands';
import { env } from './tools';
import { ImageResolvable, drawCard } from 'discord-welcome-card';

const client = new Client({
  intents: ['Guilds', 'GuildMessages', 'DirectMessages', 'GuildMembers'],
});

client.once('ready', () => {
  console.log('Discord bot is ready! 🤖');
});

client.on('guildCreate', async (guild) => {
  await deployCommands({ guildId: guild.id });
});

client.on('guildMemberAdd', async (member) => {
  const image = await drawCard({
    theme: 'circuit',
    text: {
      title: 'Hellloo',
      text: member.user.tag,
      color: `#fff`,
    },
    avatar: {
      image: member.user.avatarURL({ extension: 'png' }) as ImageResolvable,
      outlineWidth: 5,
    },
    card: {
      background: 'https://i.imgur.com/ea9PB3H.png',
      blur: 1,
      border: true,
      rounded: true,
    },
  });

  (member.guild.channels.cache.get('1043780857808293979') as TextChannel).send({
    content: `<@${member.id}> Welcome to the server!`,
    files: [image],
  });
});

client.on('guildMemberRemove', async (member) => {
  const image = await drawCard({
    theme: 'circuit',
    text: {
      title: 'Hellloo',
      text: member.user.tag,
      color: `#fff`,
    },
    avatar: {
      image: member.user.avatarURL({ extension: 'png' }) as ImageResolvable,
      outlineWidth: 5,
    },
    card: {
      background: 'https://i.imgur.com/ea9PB3H.png',
      blur: 1,
      border: true,
      rounded: true,
    },
  });

  (member.guild.channels.cache.get('1043780857808293979') as TextChannel).send({
    content: `<@${member.id}> Welcome to the server!`,
    files: [image],
  });
});

client.on('interactionCreate', async (interaction) => {
  if (!interaction.isCommand()) {
    return;
  }
  const { commandName } = interaction;
  if (commands[commandName as keyof typeof commands]) {
    commands[commandName as keyof typeof commands].execute(interaction);
  }
});

client.login(env.CLIENT_TOKEN);
