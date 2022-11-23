const { SlashCommandBuilder } = require("@discordjs/builders");
const { MessageEmbed } = require("discord.js");

module.exports = {
  data: new SlashCommandBuilder()
    .setName("ban")
    .setDescription("Allows the admin or owner to ban the member.")
    .addUserOption((option) =>
      option
        .setName("user")
        .setDescription("The person who you want to ban")
        .setRequired(true)
    )
    .addStringOption((option) =>
      option
        .setName("reason")
        .setDescription("Reason to ban member")
        .setRequired(true)
    ),
  run: async ({ client, interaction }) => {
    let member = interaction.options.getMember("user");
    let reason = interaction.options.getString("reason") || "No reason given";

    if (!member) return interaction.reply("Invalid member");

    try {
      await interaction.guild.bans.create(member, {
        reason,
      });
      return interaction.editReply({
        content: `<@${member.user.id}> has been`,
      });
    } catch (err) {
      if (err) {
        console.error(err);
        return interaction.editReply(`Failed to ban <@${member.user.id}>`);
      }
    }
  },
};
